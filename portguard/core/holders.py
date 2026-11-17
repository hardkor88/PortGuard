"""Кто на самом деле занимает COM-порт.

Windows не отдаёт эту информацию напрямую: «доступ запрещён» — и всё. Поэтому
PortGuard перечисляет хендлы всех процессов через
NtQuerySystemInformation(SystemExtendedHandleInformation), аккуратно дублирует
их в свой процесс и сравнивает имя объекта с внутренним путём порта
(COM3 -> \\Device\\Serial0, USB-порт -> \\Device\\USBSER000).

Важно: мы НЕ открываем сам порт, чтобы «проверить занятость». Открытие COM-порта
дёргает линии DTR/RTS и сбрасывает Arduino/ESP — именно этим грешат многие
«мониторы портов». Здесь порт остаётся нетронутым.
"""

from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass, field

from . import winapi as w
from .setupapi import get_dos_device_path

try:  # psutil есть в зависимостях, но приложение не должно падать без него
    import psutil
except Exception:  # pragma: no cover - защита от урезанных сборок
    psutil = None


@dataclass(slots=True)
class Holder:
    pid: int
    name: str
    path: str
    exe: str = ""

    def to_dict(self) -> dict:
        return {"pid": self.pid, "name": self.name, "path": self.path, "exe": self.exe}


@dataclass(slots=True)
class HolderReport:
    port: str
    device_path: str | None = None
    holders: list[Holder] = field(default_factory=list)
    processes_scanned: int = 0
    processes_denied: int = 0
    handles_scanned: int = 0
    partial: bool = False
    error: str = ""
    needs_admin: bool = False
    elapsed: float = 0.0
    privilege: bool = False

    @property
    def busy(self) -> bool:
        return bool(self.holders)

    def describe(self) -> str:
        if self.error:
            if self.needs_admin:
                return (
                    f"{self.port}: чтобы узнать, кто держит порт, нужны права "
                    "администратора.\n"
                    "Windows закрывает перечисление хендлов процессов "
                    "(NtQuerySystemInformation) для непривилегированных программ.\n"
                    "Запустите PortGuard от имени администратора — и PortGuard "
                    "покажет конкретные процессы и их PID."
                )
            return f"{self.port}: {self.error}"
        lines = [f"{self.port} → {self.device_path or 'путь устройства не найден'}"]
        if self.holders:
            lines.append(f"Порт занят, держателей: {len(self.holders)}")
            for holder in self.holders:
                line = f"  • {holder.name} (PID {holder.pid})"
                if holder.exe:
                    line += f"\n    {holder.exe}"
                lines.append(line)
        else:
            lines.append("Порт свободен: ни один процесс не держит его хендл.")
        if self.partial:
            lines.append(
                "Проверка не завершена (таймаут) — часть хендлов не проверена. "
                "Повторите запрос от имени администратора."
            )
        if self.processes_denied:
            lines.append(
                f"Не удалось открыть процессов: {self.processes_denied} "
                "(нужны права администратора для системных процессов)."
            )
        lines.append(
            f"Проверено процессов: {self.processes_scanned}, "
            f"хендлов: {self.handles_scanned}, "
            f"время: {self.elapsed:.2f} с"
        )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "port": self.port,
            "device_path": self.device_path,
            "busy": self.busy,
            "holders": [h.to_dict() for h in self.holders],
            "processes_scanned": self.processes_scanned,
            "processes_denied": self.processes_denied,
            "handles_scanned": self.handles_scanned,
            "partial": self.partial,
            "error": self.error,
            "needs_admin": self.needs_admin,
            "elapsed": round(self.elapsed, 3),
            "privilege": self.privilege,
        }


# ---------------------------------------------------------------------------
# Привилегии и низкоуровневые запросы
# ---------------------------------------------------------------------------
def enable_debug_privilege() -> bool:
    """Пытается включить SeDebugPrivilege (нужно для системных процессов)."""
    token = wintypes.HANDLE()
    if not w.advapi32.OpenProcessToken(
        w.kernel32.GetCurrentProcess(),
        w.TOKEN_ADJUST_PRIVILEGES | w.TOKEN_QUERY,
        ctypes.byref(token),
    ):
        return False
    try:
        luid = w.LUID()
        if not w.advapi32.LookupPrivilegeValueW(None, w.SE_DEBUG_NAME, ctypes.byref(luid)):
            return False
        privileges = w.TOKEN_PRIVILEGES()
        privileges.PrivilegeCount = 1
        privileges.Privileges[0].Luid = luid
        privileges.Privileges[0].Attributes = w.SE_PRIVILEGE_ENABLED
        if not w.advapi32.AdjustTokenPrivileges(
            token, False, ctypes.byref(privileges), 0, None, None
        ):
            return False
        return ctypes.get_last_error() == w.ERROR_SUCCESS
    finally:
        w.kernel32.CloseHandle(token)


def _query_system_handles() -> tuple[bytes, int]:
    size = 1 << 20
    while size < (1 << 28):
        buffer = ctypes.create_string_buffer(size)
        needed = wintypes.ULONG(0)
        status = w.ntdll.NtQuerySystemInformation(
            w.SystemExtendedHandleInformation, buffer, size, ctypes.byref(needed)
        )
        if status == w.STATUS_INFO_LENGTH_MISMATCH:
            size = max(needed.value + 65536, size * 2)
            continue
        if status != w.STATUS_SUCCESS:
            raise OSError(f"NtQuerySystemInformation вернул 0x{status & 0xFFFFFFFF:08X}")
        info = ctypes.cast(
            buffer, ctypes.POINTER(w.SYSTEM_HANDLE_INFORMATION_EX)
        ).contents
        return buffer, int(info.NumberOfHandles)
    raise OSError("Слишком много хендлов в системе")


def _iter_handles(buffer):
    if isinstance(buffer, (bytes, bytearray)):
        pointer = ctypes.cast(
            ctypes.c_char_p(bytes(buffer)),
            ctypes.POINTER(w.SYSTEM_HANDLE_INFORMATION_EX),
        )
    else:
        pointer = ctypes.cast(buffer, ctypes.POINTER(w.SYSTEM_HANDLE_INFORMATION_EX))
    info = pointer.contents
    count = int(info.NumberOfHandles)
    array = ctypes.cast(
        ctypes.byref(info.Handles),
        ctypes.POINTER(w.SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX * count),
    ).contents
    for entry in array:
        yield int(entry.UniqueProcessId), int(entry.HandleValue)


def _object_type_name(handle: int) -> str:
    buffer = ctypes.create_string_buffer(1024)
    needed = wintypes.ULONG(0)
    status = w.ntdll.NtQueryObject(
        wintypes.HANDLE(handle),
        w.ObjectTypeInformation,
        buffer,
        1024,
        ctypes.byref(needed),
    )
    if status != w.STATUS_SUCCESS:
        return ""
    return _read_unicode_string(buffer)


def _object_name(handle: int) -> str:
    buffer = ctypes.create_string_buffer(4096)
    needed = wintypes.ULONG(0)
    status = w.ntdll.NtQueryObject(
        wintypes.HANDLE(handle),
        w.ObjectNameInformation,
        buffer,
        4096,
        ctypes.byref(needed),
    )
    if status in (w.STATUS_INFO_LENGTH_MISMATCH, w.STATUS_BUFFER_TOO_SMALL):
        size = max(needed.value, 4096)
        buffer = ctypes.create_string_buffer(size)
        status = w.ntdll.NtQueryObject(
            wintypes.HANDLE(handle),
            w.ObjectNameInformation,
            buffer,
            size,
            ctypes.byref(needed),
        )
    if status != w.STATUS_SUCCESS:
        return ""
    return _read_unicode_string(buffer)


def _read_unicode_string(buffer) -> str:
    text = ctypes.cast(buffer, ctypes.POINTER(w.UNICODE_STRING)).contents
    if not text.Buffer or not text.Length:
        return ""
    return ctypes.wstring_at(text.Buffer, text.Length // 2)


def _duplicate(source_process, handle: int):
    target = wintypes.HANDLE()
    if not w.kernel32.DuplicateHandle(
        source_process,
        ctypes.c_void_p(handle),
        w.kernel32.GetCurrentProcess(),
        ctypes.byref(target),
        0,
        False,
        w.DUPLICATE_SAME_ACCESS,
    ):
        return None
    return target


def _process_label(pid: int) -> tuple[str, str]:
    if psutil is None:
        return f"PID {pid}", ""
    try:
        process = psutil.Process(pid)
        return process.name(), process.exe()
    except Exception:
        return f"PID {pid}", ""


# ---------------------------------------------------------------------------
# Основной сценарий
# ---------------------------------------------------------------------------
def find_port_holders(
    port: str,
    timeout: float = 8.0,
    stop_event: threading.Event | None = None,
) -> HolderReport:
    """
    Ищет процессы, держащие хендл на порт.

    Сканирование идёт в отдельном потоке: NtQueryObject может «залипнуть» на
    некоторых объектах (например, на синхронных именованных каналах), и
    замораживать интерфейс из-за этого нельзя. По таймауту возвращаются
    частичные результаты.
    """
    started = time.monotonic()
    report = HolderReport(port=port)
    device_path = get_dos_device_path(port)
    report.device_path = device_path
    if not device_path:
        report.error = "порт не найден в системе"
        report.elapsed = time.monotonic() - started
        return report

    report.privilege = enable_debug_privilege()
    stop_event = stop_event or threading.Event()

    def work() -> None:
        try:
            buffer, _ = _query_system_handles()
        except OSError as exc:
            text = str(exc)
            if "0xC0000022" in text:
                report.needs_admin = True
                report.error = "нет доступа к перечислению хендлов"
            else:
                report.error = text
            return

        by_pid: dict[int, list[int]] = {}
        for pid, handle in _iter_handles(buffer):
            report.handles_scanned += 1
            by_pid.setdefault(pid, []).append(handle)

        target = device_path.casefold()
        own_pid = w.kernel32.GetCurrentProcessId()
        for pid, handles in by_pid.items():
            if stop_event.is_set() or time.monotonic() - started > timeout:
                report.partial = True
                return
            if pid == own_pid:
                continue
            process = w.kernel32.OpenProcess(
                w.PROCESS_DUP_HANDLE | w.PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not process:
                report.processes_denied += 1
                continue
            report.processes_scanned += 1
            try:
                for handle in handles:
                    if stop_event.is_set() or time.monotonic() - started > timeout:
                        report.partial = True
                        return
                    duplicate = _duplicate(process, handle)
                    if duplicate is None:
                        continue
                    try:
                        if _object_type_name(duplicate.value) != "File":
                            continue
                        name = _object_name(duplicate.value)
                        if not name:
                            continue
                        if name.casefold() == target or name.casefold().startswith(target):
                            process_name, exe = _process_label(pid)
                            if not any(h.pid == pid for h in report.holders):
                                report.holders.append(
                                    Holder(pid=pid, name=process_name, path=name, exe=exe)
                                )
                    finally:
                        w.kernel32.CloseHandle(duplicate)
            finally:
                w.kernel32.CloseHandle(process)
        report.holders.sort(key=lambda item: (item.name.casefold(), item.pid))

    worker = threading.Thread(target=work, name="portguard-holders", daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        report.partial = True
        stop_event.set()
    report.elapsed = time.monotonic() - started
    return report


def list_busy_ports(ports: list[str], timeout: float = 6.0) -> dict[str, HolderReport]:
    """Проверяет занятость нескольких портов подряд (используется в GUI)."""
    result: dict[str, HolderReport] = {}
    for port in ports:
        result[port] = find_port_holders(port, timeout=timeout)
    return result
