"""Сбор данных об устройствах и действия над ними через SetupAPI.

Всё общение с Windows идёт через ctypes-объявления из winapi.py. Модуль не
зависит от GUI: его можно использовать из CLI и тестов.
"""

from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from dataclasses import dataclass

from . import winapi as w
from .model import Device, category_of

ERROR_INVALID_DATA = 13
ERROR_NO_SUCH_DEVINST = 0x0000042B


@dataclass(slots=True)
class ActionResult:
    ok: bool
    message: str
    detail: str = ""


# ---------------------------------------------------------------------------
# Чтение свойств
# ---------------------------------------------------------------------------
def _prop_bytes(
    hdev: wintypes.HANDLE, did: ctypes.POINTER(w.SP_DEVINFO_DATA), prop: int
) -> bytes | None:
    size = wintypes.DWORD(0)
    w.setupapi.SetupDiGetDeviceRegistryPropertyW(
        hdev, did, prop, None, None, 0, ctypes.byref(size)
    )
    if size.value == 0:
        return None
    buf = (ctypes.c_ubyte * size.value)()
    reg_type = wintypes.DWORD()
    ok = w.setupapi.SetupDiGetDeviceRegistryPropertyW(
        hdev, did, prop, ctypes.byref(reg_type), buf, size, ctypes.byref(size)
    )
    if not ok:
        return None
    return bytes(buf[: size.value])


def _prop_str(hdev, did, prop: int) -> str:
    raw = _prop_bytes(hdev, did, prop)
    if not raw:
        return ""
    return raw.decode("utf-16-le", "ignore").rstrip("\x00")


def _prop_list(hdev, did, prop: int) -> tuple[str, ...]:
    raw = _prop_bytes(hdev, did, prop)
    if not raw:
        return ()
    parts = raw.decode("utf-16-le", "ignore").split("\x00")
    return tuple(part for part in parts if part)


def _devprop(hdev, did, key: w.DEVPROPKEY):
    """Читает DEVPKEY; возвращает строку, список строк или None."""
    required = wintypes.DWORD(0)
    prop_type = w.DEVPROPTYPE()
    w.setupapi.SetupDiGetDevicePropertyW(
        hdev, did, ctypes.byref(key), ctypes.byref(prop_type),
        None, 0, ctypes.byref(required), 0,
    )
    if required.value == 0:
        return None
    buf = (ctypes.c_ubyte * required.value)()
    ok = w.setupapi.SetupDiGetDevicePropertyW(
        hdev, did, ctypes.byref(key), ctypes.byref(prop_type),
        buf, required, ctypes.byref(required), 0,
    )
    if not ok:
        return None
    raw = bytes(buf[: required.value])
    if prop_type.value in (w.DEVPROP_TYPE_STRING, w.DEVPROP_TYPE_STRING_LIST):
        text = raw.decode("utf-16-le", "ignore").rstrip("\x00")
        if prop_type.value == w.DEVPROP_TYPE_STRING_LIST:
            return tuple(part for part in text.split("\x00") if part)
        return text
    return None


def _key(d1: int, d2: int, d3: int, d4: bytes, pid: int) -> w.DEVPROPKEY:
    key = w.DEVPROPKEY()
    key.fmtid = w.GUID(d1, d2, d3, (ctypes.c_ubyte * 8)(*d4))
    key.pid = pid
    return key


KEY_BUS_REPORTED_DESC = _key(
    0x540B947E, 0x8B40, 0x45BC, b"\xa8\xa2\x6a\x0b\x89\x4c\xbd\xa2", 4
)
KEY_DRIVER_VERSION = _key(
    0xA8B865DD, 0x2E3D, 0x4094, b"\xad\x97\xe5\x93\xa7\x0c\x75\xd6", 3
)
KEY_LOCATION_PATHS = _key(
    0xA45C254E, 0xDF1C, 0x4EFD, b"\x80\x20\x67\xd1\x46\xa8\x50\xe0", 37
)


def _read_port_name(hdev, did) -> str | None:
    """Имя COM-порта из ключа Device Parameters (значение PortName)."""
    hkey = w.setupapi.SetupDiOpenDevRegKey(
        hdev, did, w.DICS_FLAG_GLOBAL, 0, w.DIREG_DEV, w.KEY_READ
    )
    if not hkey or hkey == w.INVALID_HANDLE_VALUE:
        return None
    try:
        size = wintypes.DWORD(0)
        rc = w.advapi32.RegQueryValueExW(
            hkey, "PortName", None, None, None, ctypes.byref(size)
        )
        if rc != w.ERROR_SUCCESS or size.value == 0:
            return None
        buf = (ctypes.c_ubyte * size.value)()
        rc = w.advapi32.RegQueryValueExW(
            hkey, "PortName", None, None, buf, ctypes.byref(size)
        )
        if rc != w.ERROR_SUCCESS:
            return None
        return bytes(buf[: size.value]).decode("utf-16-le", "ignore").rstrip("\x00")
    finally:
        w.advapi32.RegCloseKey(hkey)


def _devnode_status(devinst: int) -> tuple[int, int]:
    status = wintypes.ULONG(0)
    problem = wintypes.ULONG(0)
    rc = w.cfgmgr32.CM_Get_DevNode_Status(
        ctypes.byref(status), ctypes.byref(problem), devinst, 0
    )
    if rc != w.CR_SUCCESS:
        return 0, 0
    return status.value, problem.value


def _parent_id(devinst: int) -> str | None:
    parent = w.DEVINST(0)
    if w.cfgmgr32.CM_Get_Parent(ctypes.byref(parent), devinst, 0) != w.CR_SUCCESS:
        return None
    return _device_id(parent.value)


def _device_id(devinst: int) -> str | None:
    buf = ctypes.create_unicode_buffer(512)
    if w.cfgmgr32.CM_Get_Device_IDW(devinst, buf, 512, 0) != w.CR_SUCCESS:
        return None
    return buf.value


# ---------------------------------------------------------------------------
# Перечисление
# ---------------------------------------------------------------------------
def enumerate_devices() -> list[Device]:
    """Возвращает все присутствующие сейчас PnP-устройства."""
    hdev = w.setupapi.SetupDiGetClassDevsW(
        None, None, None, w.DIGCF_ALLCLASSES | w.DIGCF_PRESENT
    )
    if not hdev or hdev == w.INVALID_HANDLE_VALUE:
        raise OSError(
            ctypes.get_last_error() or 0, "SetupDiGetClassDevsW не вернул список"
        )

    devices: list[Device] = []
    try:
        did = w.SP_DEVINFO_DATA()
        did.cbSize = ctypes.sizeof(w.SP_DEVINFO_DATA)
        index = 0
        while w.setupapi.SetupDiEnumDeviceInfo(hdev, index, ctypes.byref(did)):
            index += 1
            try:
                device = _build_device(hdev, did)
            except Exception:
                # Одно «странное» устройство не должно ронять весь список.
                continue
            if device is not None:
                devices.append(device)
    finally:
        w.setupapi.SetupDiDestroyDeviceInfoList(hdev)
    return devices


def _build_device(hdev, did) -> Device | None:
    id_buf = ctypes.create_unicode_buffer(512)
    needed = wintypes.DWORD(0)
    if not w.setupapi.SetupDiGetDeviceInstanceIdW(
        hdev, ctypes.byref(did), id_buf, 512, ctypes.byref(needed)
    ):
        return None
    instance_id = id_buf.value
    if not instance_id:
        return None

    hardware_ids = _prop_list(hdev, ctypes.byref(did), w.SPDRP_HARDWAREID)
    compatible_ids = _prop_list(hdev, ctypes.byref(did), w.SPDRP_COMPATIBLEIDS)
    status, problem = _devnode_status(did.DevInst)
    install_raw = _prop_bytes(hdev, ctypes.byref(did), w.SPDRP_INSTALL_STATE)
    install_state = struct.unpack("<I", install_raw[:4])[0] if install_raw and len(install_raw) >= 4 else 0

    location_paths = _devprop(hdev, ctypes.byref(did), KEY_LOCATION_PATHS) or ()
    if isinstance(location_paths, str):
        location_paths = (location_paths,)

    bus_reported = _devprop(hdev, ctypes.byref(did), KEY_BUS_REPORTED_DESC) or ""
    if not isinstance(bus_reported, str):
        bus_reported = ""
    driver_version = _devprop(hdev, ctypes.byref(did), KEY_DRIVER_VERSION) or ""
    if not isinstance(driver_version, str):
        driver_version = ""

    device = Device(
        instance_id=instance_id,
        name=_prop_str(hdev, ctypes.byref(did), w.SPDRP_FRIENDLYNAME),
        description=_prop_str(hdev, ctypes.byref(did), w.SPDRP_DEVICEDESC),
        device_class=_prop_str(hdev, ctypes.byref(did), w.SPDRP_CLASS),
        class_guid=_prop_str(hdev, ctypes.byref(did), w.SPDRP_CLASSGUID),
        manufacturer=_prop_str(hdev, ctypes.byref(did), w.SPDRP_MFG),
        service=_prop_str(hdev, ctypes.byref(did), w.SPDRP_SERVICE),
        enumerator=_prop_str(hdev, ctypes.byref(did), w.SPDRP_ENUMERATOR_NAME),
        location=_prop_str(hdev, ctypes.byref(did), w.SPDRP_LOCATION_INFORMATION),
        location_paths=tuple(location_paths),
        bus_reported_desc=bus_reported,
        driver_version=driver_version,
        hardware_ids=hardware_ids,
        compatible_ids=compatible_ids,
        com_port=_read_port_name(hdev, ctypes.byref(did)),
        parent_id=_parent_id(did.DevInst),
        started=bool(status & w.DN_STARTED),
        problem=problem,
        disableable=bool(status & w.DN_DISABLEABLE),
        removable=bool(status & w.DN_REMOVABLE),
        install_state=install_state,
    )

    from .model import parse_serial, parse_vid_pid

    device.vid, device.pid = parse_vid_pid((instance_id,) + hardware_ids)
    device.serial = parse_serial(instance_id)
    if not device.name:
        device.name = device.description or instance_id
    device.category = category_of(device)
    return device


# ---------------------------------------------------------------------------
# Действия
# ---------------------------------------------------------------------------
def _open_devnode(instance_id: str):
    """
    Открывает набор устройств с одним нужным элементом.

    SetupDiCreateDeviceInfoList + SetupDiOpenDeviceInfoW дешевле, чем
    перечисление всех устройств ради одного.
    """
    hdev = w.setupapi.SetupDiCreateDeviceInfoList(None, None)
    if not hdev or hdev == w.INVALID_HANDLE_VALUE:
        raise OSError(ctypes.get_last_error() or 0, "Не удалось создать набор устройств")
    did = w.SP_DEVINFO_DATA()
    did.cbSize = ctypes.sizeof(w.SP_DEVINFO_DATA)
    if not w.setupapi.SetupDiOpenDeviceInfoW(
        hdev, instance_id, None, 0, ctypes.byref(did)
    ):
        err = ctypes.get_last_error()
        w.setupapi.SetupDiDestroyDeviceInfoList(hdev)
        raise OSError(err or 0, f"Устройство не найдено: {instance_id}")
    return hdev, did


def _property_change(hdev, did, state_change: int, scope: int) -> bool:
    params = w.SP_PROPCHANGE_PARAMS()
    params.ClassInstallHeader.cbSize = ctypes.sizeof(w.SP_CLASSINSTALL_HEADER)
    params.ClassInstallHeader.InstallFunction = w.DIF_PROPERTYCHANGE
    params.StateChange = state_change
    params.Scope = scope
    params.HwProfile = 0
    if not w.setupapi.SetupDiSetClassInstallParamsW(
        hdev,
        ctypes.byref(did),
        ctypes.cast(ctypes.byref(params), ctypes.POINTER(w.SP_CLASSINSTALL_HEADER)),
        ctypes.sizeof(params),
    ):
        return False
    return bool(
        w.setupapi.SetupDiCallClassInstaller(
            w.DIF_PROPERTYCHANGE, hdev, ctypes.byref(did)
        )
    )


def set_device_enabled(instance_id: str, enabled: bool) -> ActionResult:
    """Включает или отключает устройство (нужны права администратора)."""
    try:
        hdev, did = _open_devnode(instance_id)
    except OSError as exc:
        return ActionResult(False, str(exc))
    try:
        state = w.DICS_ENABLE if enabled else w.DICS_DISABLE
        if not _property_change(hdev, did, state, w.DICS_FLAG_GLOBAL):
            err = ctypes.get_last_error()
            return ActionResult(
                False,
                "Windows отклонила изменение состояния",
                f"Ошибка {err}. Обычно это значит, что нужны права администратора "
                "или устройство нельзя переключить.",
            )
        if enabled:
            # Для включения нужен ещё один проход в контексте конфигурации.
            _property_change(hdev, did, w.DICS_ENABLE, w.DICS_FLAG_CONFIGSPECIFIC)
        return ActionResult(
            True,
            "Устройство включено" if enabled else "Устройство отключено",
        )
    finally:
        w.setupapi.SetupDiDestroyDeviceInfoList(hdev)


def restart_device(instance_id: str) -> ActionResult:
    """Перезапускает устройство (DICS_PROPCHANGE)."""
    try:
        hdev, did = _open_devnode(instance_id)
    except OSError as exc:
        return ActionResult(False, str(exc))
    try:
        if not _property_change(hdev, did, w.DICS_PROPCHANGE, w.DICS_FLAG_GLOBAL):
            err = ctypes.get_last_error()
            return ActionResult(False, "Не удалось перезапустить устройство", f"Ошибка {err}")
        _property_change(hdev, did, w.DICS_PROPCHANGE, w.DICS_FLAG_CONFIGSPECIFIC)
        return ActionResult(True, "Устройство перезапущено")
    finally:
        w.setupapi.SetupDiDestroyDeviceInfoList(hdev)


VETO_TEXT = {
    w.PNP_VETO_UNKNOWN: "неизвестная причина",
    w.PNP_VETO_LEGACY_DEVICE: "устройство устаревшего типа",
    w.PNP_VETO_PENDING_CLOSE: "есть незакрытые файлы",
    w.PNP_VETO_WINDOWS_APP: "приложение использует устройство",
    w.PNP_VETO_WINDOWS_SERVICE: "служба Windows использует устройство",
    w.PNP_VETO_OUTSTANDING_OPEN: "есть открытые дескрипторы",
    w.PNP_VETO_DEVICE: "устройство занято",
    w.PNP_VETO_DRIVER: "драйвер запретил извлечение",
    w.PNP_VETO_ILLEGAL_DEVICE_REQUEST: "недопустимый запрос к устройству",
    w.PNP_VETO_INSUFFICIENT_POWER: "не хватает питания",
    w.PNP_VETO_NON_DISABLEABLE: "устройство нельзя отключать",
    w.PNP_VETO_LEGACY_DRIVER: "драйвер устаревшего типа",
    w.PNP_VETO_INSUFFICIENT_RIGHTS: "не хватает прав",
}


def eject_device(instance_id: str) -> ActionResult:
    """Безопасно извлекает устройство (CM_Request_Device_EjectW)."""
    devinst = w.DEVINST(0)
    rc = w.cfgmgr32.CM_Locate_DevNodeW(
        ctypes.byref(devinst), instance_id, 0
    )
    if rc != w.CR_SUCCESS:
        return ActionResult(False, "Устройство не найдено", f"CONFIGRET 0x{rc:08X}")

    veto = ctypes.c_int(0)
    veto_name = ctypes.create_unicode_buffer(260)
    rc = w.cfgmgr32.CM_Request_Device_EjectW(
        devinst.value, ctypes.byref(veto), veto_name, 260, w.CM_EJECT_NORMAL
    )
    if rc == w.CR_REMOVE_VETOED:
        reason = VETO_TEXT.get(veto.value, f"вето типа {veto.value}")
        who = veto_name.value or ""
        detail = f"Причина: {reason}" + (f" — {who}" if who else "")
        return ActionResult(False, "Windows не разрешила извлечь устройство", detail)
    if rc != w.CR_SUCCESS:
        return ActionResult(False, "Не удалось извлечь устройство", f"CONFIGRET 0x{rc:08X}")
    return ActionResult(True, "Устройство извлечено")


# ---------------------------------------------------------------------------
# Вспомогательное
# ---------------------------------------------------------------------------
def get_dos_device_path(port_name: str) -> str | None:
    """COM3 -> \\Device\\Serial0 (внутренний путь устройства)."""
    buf = ctypes.create_unicode_buffer(1024)
    length = w.kernel32.QueryDosDeviceW(port_name, buf, 1024)
    if not length:
        return None
    return buf.value


def open_device_manager() -> None:
    """Открывает системный Диспетчер устройств."""
    w.shell32.ShellExecuteW(None, "open", "devmgmt.msc", None, None, 1)
