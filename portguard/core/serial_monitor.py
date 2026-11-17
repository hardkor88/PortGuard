"""COM-терминал: чтение, запись и управление линиями DTR/RTS.

Модуль ничего не знает про GUI: отдаёт данные через колбэки, поэтому его
используют и оконное приложение, и консольная команда `portguard monitor`.

Отдельно реализованы последовательности сброса: у Arduino это импульс DTR,
у ESP32 — «танец» DTR/RTS, который переводит чип в режим загрузчика.
"""

from __future__ import annotations

import threading
import time
from typing import Callable

try:
    import serial
except Exception:  # pragma: no cover - pyserial обязателен, но сообщим понятно
    serial = None


class SerialPortError(RuntimeError):
    pass


class SerialSession:
    """Одна открытая сессия с COM-портом."""

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        on_data: Callable[[bytes], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ):
        self.port = port
        self.baudrate = baudrate
        self.on_data = on_data
        self.on_error = on_error
        self.rx_bytes = 0
        self.tx_bytes = 0
        self.last_error = ""
        self._serial = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._write_lock = threading.Lock()

    # -- состояние ----------------------------------------------------------
    @property
    def is_open(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    # -- открытие/закрытие --------------------------------------------------
    def open(self) -> None:
        if serial is None:
            raise SerialPortError("Модуль pyserial не установлен: pip install pyserial")
        if self.is_open:
            return
        try:
            self._serial = serial.Serial(
                self.port,
                baudrate=self.baudrate,
                timeout=0.05,
                write_timeout=2.0,
            )
        except Exception as exc:
            raise SerialPortError(self._explain(exc)) from exc
        self._stop.clear()
        try:
            self._serial.reset_input_buffer()
        except Exception:
            pass

    def close(self) -> None:
        self._stop.set()
        if self._reader:
            self._reader.join(timeout=1.0)
            self._reader = None
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None

    def _explain(self, exc: Exception) -> str:
        text = str(exc)
        if "Access is denied" in text or "Отказано в доступе" in text:
            return (
                f"{self.port} занят другой программой. "
                "Кнопка «Кто занял порт» покажет виновника (нужен запуск от админа)."
            )
        if "could not open port" in text.lower():
            return f"Не удалось открыть {self.port}: {text}"
        return f"Ошибка {self.port}: {text}"

    # -- чтение -------------------------------------------------------------
    def start_reader(self) -> None:
        if self._reader and self._reader.is_alive():
            return
        self._stop.clear()
        self._reader = threading.Thread(
            target=self._read_loop, name="portguard-serial", daemon=True
        )
        self._reader.start()

    def _read_loop(self) -> None:
        while not self._stop.is_set() and self.is_open:
            try:
                data = self._serial.read(4096)
            except Exception as exc:
                self.last_error = str(exc)
                if self.on_error:
                    try:
                        self.on_error(str(exc))
                    except Exception:
                        pass
                return
            if data:
                self.rx_bytes += len(data)
                if self.on_data:
                    try:
                        self.on_data(data)
                    except Exception:
                        pass

    def read_nowait(self) -> bytes:
        """Чтение для консольного режима (без потока)."""
        if not self.is_open:
            return b""
        try:
            data = self._serial.read(4096)
        except Exception as exc:
            self.last_error = str(exc)
            return b""
        if data:
            self.rx_bytes += len(data)
        return data

    # -- запись -------------------------------------------------------------
    def write(self, data: bytes) -> int:
        if not self.is_open:
            raise SerialPortError("Порт не открыт")
        with self._write_lock:
            try:
                written = self._serial.write(data)
            except Exception as exc:
                raise SerialPortError(self._explain(exc)) from exc
        self.tx_bytes += written or 0
        return written or 0

    def send_text(
        self,
        text: str,
        line_ending: str = "\\n",
        encoding: str = "utf-8",
        as_hex: bool = False,
    ) -> int:
        if as_hex:
            payload = self._parse_hex(text)
        else:
            payload = text.encode(encoding, "replace") + _ending_bytes(line_ending)
        return self.write(payload)

    @staticmethod
    def _parse_hex(text: str) -> bytes:
        cleaned = text.replace(",", " ").replace("0x", " ").replace("0X", " ")
        parts = [part for part in cleaned.split() if part]
        try:
            return bytes(int(part, 16) for part in parts)
        except ValueError as exc:
            raise SerialPortError(f"Некорректный HEX: {text}") from exc

    # -- линии --------------------------------------------------------------
    def set_dtr(self, value: bool) -> None:
        if self.is_open:
            self._serial.dtr = value

    def set_rts(self, value: bool) -> None:
        if self.is_open:
            self._serial.rts = value

    def set_baudrate(self, baudrate: int) -> None:
        self.baudrate = baudrate
        if self.is_open:
            self._serial.baudrate = baudrate

    # -- сброс --------------------------------------------------------------
    def pulse_dtr(self) -> None:
        """Классический сброс Arduino: короткий импульс DTR."""
        self.set_dtr(False)
        time.sleep(0.05)
        self.set_dtr(True)
        time.sleep(0.05)

    def esp_reset(self) -> None:
        """Сброс ESP32/ESP8266 по линии EN (RTS)."""
        self.set_rts(True)
        time.sleep(0.12)
        self.set_rts(False)
        time.sleep(0.05)

    def esp_bootloader(self) -> None:
        """
        Переводит ESP32 в режим загрузчика (IO0=LOW, затем импульс EN).

        Последовательность повторяет то, что делает esptool.
        """
        self.set_dtr(False)  # IO0 = HIGH
        self.set_rts(True)  # EN = LOW, чип в сбросе
        time.sleep(0.12)
        self.set_dtr(True)  # IO0 = LOW
        self.set_rts(False)  # EN = HIGH, чип выходит из сброса
        time.sleep(0.05)
        self.set_dtr(False)  # IO0 = HIGH


def _ending_bytes(name: str) -> bytes:
    mapping = {
        "none": b"",
        "\\n": b"\n",
        "\\r": b"\r",
        "\\r\\n": b"\r\n",
        "cr": b"\r",
        "lf": b"\n",
        "crlf": b"\r\n",
    }
    return mapping.get(name, b"\n")
