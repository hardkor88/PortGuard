"""Модель устройства и справочники: категории, VID/PID, коды проблем.

Модуль не вызывает Win32 — он только описывает данные, которые собирает
setupapi.py, и умеет их «очеловечивать»: подписи статусов, названия чипов,
группировку по категориям.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Iterable, Sequence

PORT_CLASS_GUID = "4d36e978-e325-11ce-bfc1-08002be10318"

# ---------------------------------------------------------------------------
# Категории. Порядок важен: он же порядок в боковой панели.
# ---------------------------------------------------------------------------
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("all", "Все устройства"),
    ("usb", "USB"),
    ("ports", "Порты COM/LPT"),
    ("hid", "Клавиатуры и мыши"),
    ("bluetooth", "Bluetooth"),
    ("audio", "Звук"),
    ("display", "Дисплеи"),
    ("network", "Сеть"),
    ("camera", "Камеры"),
    ("storage", "Накопители"),
    ("problem", "С проблемами"),
    ("other", "Прочее"),
)

CATEGORY_TITLES = dict(CATEGORIES)

# Классы устройств (SPDRP_CLASS), по которым раскладываем без анализа ID.
_CLASS_CATEGORIES = {
    "ports": "ports",
    "modem": "ports",
    "usb": "usb",
    "hidclass": "hid",
    "keyboard": "hid",
    "mouse": "hid",
    "bluetooth": "bluetooth",
    "bluetoothradio": "bluetooth",
    "media": "audio",
    "audioendpoint": "audio",
    "sound": "audio",
    "monitor": "display",
    "display": "display",
    "displayadapters": "display",
    "net": "network",
    "nettrans": "network",
    "camera": "camera",
    "image": "camera",
    "mediacapture": "camera",
    "diskdrive": "storage",
    "volume": "storage",
    "usbstor": "storage",
    "cdrom": "storage",
    "floppydisk": "storage",
    "scsiadapter": "storage",
    "hdc": "storage",
    "smartcardreader": "other",
    "printer": "other",
    "system": "other",
    "processor": "other",
    "firmware": "other",
    "securitydevices": "other",
}

# Проблемные коды -> короткая причина (по cfg.h и кодам Диспетчера устройств).
PROBLEM_TEXT = {
    0: "",
    1: "Устройство не настроено",
    2: "Не удалось загрузить драйвер устройства",
    3: "Не хватает памяти",
    4: "Неверный тип записи в реестре",
    5: "Не удалось распределить ресурсы",
    6: "Конфликт конфигурации загрузки",
    7: "Отказ фильтр-драйвера",
    8: "Загрузчик драйвера не найден",
    9: "Неверные данные в реестре",
    10: "Устройство не запускается (код 10)",
    11: "Устройство сообщает о неверных возможностях",
    12: "Конфликт ресурсов (код 12)",
    13: "Устройство не проверено",
    14: "Нужна перезагрузка (код 14)",
    15: "Требуется переподключение",
    16: "Частично настроено",
    17: "Неизвестный ресурс",
    18: "Нужна переустановка драйвера",
    19: "Ошибка реестра",
    20: "Драйвер виртуального устройства (VxD)",
    21: "Устройство будет удалено",
    22: "Отключено",
    23: "Драйвер не готов",
    24: "Устройство не подключено (код 24)",
    25: "Устройство перемещено",
    26: "Слишком рано для запуска",
    27: "Нет корректной логической конфигурации",
    28: "Драйвер не установлен (код 28)",
    29: "Отключено на уровне оборудования",
    30: "Не удалось разделить IRQ",
    31: "Не удалось добавить устройство",
    32: "Служба устройства отключена",
    33: "Не удалось перевести ресурсы",
    34: "Нет программной конфигурации",
    35: "Ошибка таблицы BIOS",
    36: "Не удалось перевести IRQ",
    37: "Не удалось загрузить драйвер (код 37)",
    38: "Не удалось выгрузить предыдущий драйвер",
    39: "Повреждён или отсутствует драйвер (код 39)",
    40: "Неверный ключ службы драйвера",
    41: "Устаревшая служба без устройств",
    42: "Дубликат устройства",
    43: "Устройство сообщило о сбое (код 43)",
    44: "Устройство остановлено",
    45: "Устройство отсутствует (призрак)",
    46: "Система завершает работу",
    47: "Устройство удерживается для извлечения",
    48: "Драйвер заблокирован политикой",
    49: "Слишком большой реестр устройств",
    50: "Не удалось применить свойства",
    51: "Ожидание зависимостей",
    52: "Драйвер без цифровой подписи (код 52)",
    53: "Устройство используется отладчиком",
    54: "Устройство сброшено",
    55: "Консоль заблокирована",
    56: "Нужна настройка класса",
    57: "Не удалось назначить гостевой доступ",
}

STATUS_OK = "ok"
STATUS_DISABLED = "disabled"
STATUS_ERROR = "error"
STATUS_ABSENT = "absent"
STATUS_STOPPED = "stopped"

PROBLEM_PRIORITY = {
    STATUS_DISABLED: 0,
    STATUS_ERROR: 1,
    STATUS_OK: 2,
    STATUS_STOPPED: 3,
    STATUS_ABSENT: 4,
}

# ---------------------------------------------------------------------------
# Справочники USB
# ---------------------------------------------------------------------------
VENDORS = {
    0x2341: "Arduino",
    0x2A03: "Arduino (org)",
    0x303A: "Espressif",
    0x10C4: "Silicon Labs",
    0x1A86: "WCH",
    0x0403: "FTDI",
    0x067B: "Prolific",
    0x0483: "STMicroelectronics",
    0x2E8A: "Raspberry Pi",
    0x239A: "Adafruit",
    0x1B4F: "SparkFun",
    0x04D8: "Microchip",
    0x03EB: "Atmel",
    0x1915: "Nordic Semiconductor",
    0x1366: "SEGGER",
    0x0BDA: "Realtek",
    0x8086: "Intel",
    0x8087: "Intel",
    0x045E: "Microsoft",
    0x046D: "Logitech",
    0x04E8: "Samsung",
    0x05AC: "Apple",
    0x054C: "Sony",
    0x18D1: "Google",
    0x0451: "Texas Instruments",
    0x1FC9: "NXP",
    0x04B4: "Cypress",
    0x04F2: "Chicony",
    0x0BC2: "Seagate",
    0x048D: "ITE Tech",
    0x0C45: "Sonix",
    0x13D3: "IMC Networks",
    0x0A5C: "Broadcom",
    0x04CA: "Lite-On",
    0x17EF: "Lenovo",
    0x1BCF: "Sunplus",
    0x2F8A: "SunplusIT",
    0x1B3B: "Onkyo",
    0x8564: "Transcend",
    0x090C: "Silicon Motion",
    0x13FE: "Phison",
    0x0781: "SanDisk",
    0x1058: "WD",
    0x0930: "Toshiba",
    0x152D: "JMicron",
}

# Конкретные пары VID/PID, в которых мы уверены.
CHIPS = {
    (0x1A86, 0x7523): "CH340 / CH341 (USB-UART)",
    (0x1A86, 0x5523): "CH341A (USB-UART)",
    (0x1A86, 0x7522): "CH340K (USB-UART)",
    (0x1A86, 0x55D4): "CH9102 (USB-UART)",
    (0x1A86, 0x55D3): "CH343 (USB-UART)",
    (0x10C4, 0xEA60): "CP2102 / CP210x (USB-UART)",
    (0x10C4, 0xEA70): "CP2105 (USB-UART)",
    (0x10C4, 0xEA71): "CP2108 (USB-UART)",
    (0x0403, 0x6001): "FT232R (USB-UART)",
    (0x0403, 0x6010): "FT2232 (USB-UART)",
    (0x0403, 0x6011): "FT4232 (USB-UART)",
    (0x0403, 0x6014): "FT232H (USB-UART)",
    (0x0403, 0x6015): "FT231X (USB-UART)",
    (0x067B, 0x2303): "PL2303 (USB-UART)",
    (0x303A, 0x1001): "ESP32-S2/S3 (USB Serial/JTAG)",
    (0x303A, 0x0002): "ESP32-S2 (USB OTG)",
    (0x2E8A, 0x0005): "Raspberry Pi Pico (USB CDC)",
    (0x2E8A, 0x000A): "Raspberry Pi Pico 2 (USB CDC)",
    (0x0483, 0x5740): "STM32 (USB CDC)",
    (0x2341, 0x0043): "Arduino Uno R3",
    (0x2341, 0x0042): "Arduino Mega 2560",
    (0x2341, 0x8036): "Arduino Leonardo",
    (0x2341, 0x8037): "Arduino Micro",
    (0x1366, 0x0105): "J-Link (SEGGER)",
    (0x1366, 0x0101): "J-Link (SEGGER)",
}

# Эвристика по описанию — на случай, когда VID/PID нестандартный.
_CHIP_HINTS = (
    ("ch340", "CH340 (USB-UART)"),
    ("ch341", "CH340 / CH341 (USB-UART)"),
    ("ch9102", "CH9102 (USB-UART)"),
    ("ch343", "CH343 (USB-UART)"),
    ("cp210", "CP210x (USB-UART)"),
    ("ft232", "FT232 (USB-UART)"),
    ("ft231", "FT231X (USB-UART)"),
    ("ftdi", "FTDI (USB-UART)"),
    ("pl2303", "PL2303 (USB-UART)"),
    ("prolific", "Prolific (USB-UART)"),
    ("esp32", "ESP32"),
    ("esp8266", "ESP8266"),
    ("arduino", "Arduino"),
    ("stm32", "STM32"),
    ("raspberry pi pico", "Raspberry Pi Pico"),
    ("segger", "SEGGER J-Link"),
)

_VID_PID_RE = re.compile(r"VID_([0-9A-F]{4})&PID_([0-9A-F]{4})", re.IGNORECASE)
_VID_RE = re.compile(r"VID_([0-9A-F]{4})", re.IGNORECASE)


def parse_vid_pid(ids: Iterable[str]) -> tuple[int | None, int | None]:
    """Достаёт VID/PID из списка hardware id или instance id."""
    for raw in ids:
        if not raw:
            continue
        match = _VID_PID_RE.search(raw)
        if match:
            return int(match.group(1), 16), int(match.group(2), 16)
    for raw in ids:
        if not raw:
            continue
        match = _VID_RE.search(raw)
        if match:
            return int(match.group(1), 16), None
    return None, None


def parse_serial(instance_id: str) -> str | None:
    """Серийник из instance id вида USB\\VID_1234&PID_5678\\5&1a2b3c&0&1."""
    if "\\" not in instance_id:
        return None
    tail = instance_id.rsplit("\\", 1)[-1]
    if not tail or "&" in tail:
        return None
    if len(tail) < 4:
        return None
    return tail


@dataclass(slots=True)
class Device:
    """Одно устройство из дерева PnP."""

    instance_id: str
    name: str = ""
    description: str = ""
    device_class: str = ""
    class_guid: str = ""
    manufacturer: str = ""
    service: str = ""
    enumerator: str = ""
    location: str = ""
    location_paths: tuple[str, ...] = ()
    bus_reported_desc: str = ""
    driver_version: str = ""
    hardware_ids: tuple[str, ...] = ()
    compatible_ids: tuple[str, ...] = ()
    vid: int | None = None
    pid: int | None = None
    serial: str | None = None
    com_port: str | None = None
    parent_id: str | None = None
    started: bool = False
    problem: int = 0
    disableable: bool = False
    removable: bool = False
    install_state: int = 0
    present: bool = True
    category: str = "other"

    # -- производные свойства ------------------------------------------------
    @property
    def status_kind(self) -> str:
        if not self.present:
            return STATUS_ABSENT
        if self.problem == 22:  # CM_PROB_DISABLED
            return STATUS_DISABLED
        if self.problem:
            return STATUS_ERROR
        if not self.started:
            return STATUS_STOPPED
        return STATUS_OK

    @property
    def status_text(self) -> str:
        kind = self.status_kind
        if kind == STATUS_OK:
            return "Работает"
        if kind == STATUS_DISABLED:
            return "Отключено"
        if kind == STATUS_ABSENT:
            return "Не подключено"
        if kind == STATUS_STOPPED:
            return "Остановлено"
        reason = PROBLEM_TEXT.get(self.problem, f"Ошибка (код {self.problem})")
        return reason

    @property
    def short_status(self) -> str:
        """Короткая подпись для узкой колонки таблицы."""
        kind = self.status_kind
        if kind == STATUS_OK:
            return "Работает"
        if kind == STATUS_DISABLED:
            return "Отключено"
        if kind == STATUS_ABSENT:
            return "Нет"
        if kind == STATUS_STOPPED:
            return "Остановлено"
        return f"Ошибка {self.problem}"

    @property
    def has_problem(self) -> bool:        # «Остановлено» без кода ошибки — это штатное состояние пассивных
        # устройств (ACPI-ресурсы, шины), Диспетчер устройств тоже считает их
        # нормальными. Проблема — только отключение или код ошибки.
        return self.status_kind in (STATUS_DISABLED, STATUS_ERROR)

    @property
    def vid_pid_text(self) -> str:
        if self.vid is None:
            return ""
        if self.pid is None:
            return f"{self.vid:04X}:"
        return f"{self.vid:04X}:{self.pid:04X}"

    @property
    def vendor_name(self) -> str:
        if self.vid is not None:
            return VENDORS.get(self.vid, "")
        return ""

    @property
    def chip_name(self) -> str:
        """Название чипа/платы, если узнали."""
        if self.vid is not None and self.pid is not None:
            known = CHIPS.get((self.vid, self.pid))
            if known:
                return known
        haystack = " ".join(
            filter(None, (self.name, self.description, self.bus_reported_desc))
        ).lower()
        for needle, label in _CHIP_HINTS:
            if needle in haystack:
                return label
        return ""

    @property
    def is_usb(self) -> bool:
        if self.enumerator.upper() == "USB":
            return True
        return self.instance_id.upper().startswith(("USB\\", "USBSTOR\\"))

    @property
    def is_port(self) -> bool:
        return bool(self.com_port)

    @property
    def display_name(self) -> str:
        return self.name or self.description or self.instance_id

    def to_dict(self) -> dict:
        data = asdict(self)
        data.update(
            {
                "status": self.status_text,
                "status_kind": self.status_kind,
                "vendor": self.vendor_name,
                "chip": self.chip_name,
                "vid_pid": self.vid_pid_text,
            }
        )
        return data


def category_of(device: Device) -> str:
    """Определяет категорию устройства для боковой панели."""
    if device.com_port:
        return "ports"
    cls = device.device_class.strip().lower()
    if cls in _CLASS_CATEGORIES:
        return _CLASS_CATEGORIES[cls]
    inst = device.instance_id.upper()
    if inst.startswith(("USB\\", "USBSTOR\\", "USBPRINT\\")) or device.enumerator.upper() == "USB":
        return "usb"
    if inst.startswith(("BTHENUM\\", "BTHLE\\", "BTHHFENUM\\")):
        return "bluetooth"
    if inst.startswith(("HID\\",)):
        return "hid"
    if inst.startswith(("SWD\\", "ROOT\\")):
        return "other"
    if device.vid is not None:
        return "usb"
    return "other"


def sort_key(device: Device) -> tuple:
    """Порядок в таблице: сначала проблемные, затем по категории и имени."""
    return (
        PROBLEM_PRIORITY.get(device.status_kind, 9),
        CATEGORY_TITLES.get(device.category, "я"),
        device.display_name.casefold(),
    )


def summary(devices: Sequence[Device]) -> dict[str, int]:
    """Счётчики для боковой панели и статус-бара."""
    counts: dict[str, int] = {key: 0 for key, _ in CATEGORIES}
    counts["all"] = len(devices)
    for device in devices:
        counts[device.category] = counts.get(device.category, 0) + 1
        if device.has_problem:
            counts["problem"] += 1
    return counts
