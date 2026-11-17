"""Наблюдение за hot-plug через скрытое окно и WM_DEVICECHANGE.

Регистрировать интерфейсы не нужно: Windows рассылает DBT_DEVNODES_CHANGED
всем окнам верхнего уровня при любом изменении дерева устройств. Держим
невидимое окно в отдельном потоке, поэтому GUI реагирует на подключение
флешки или платы мгновенно, без опроса раз в секунду.
"""

from __future__ import annotations

import ctypes
import os
import threading
import time
from typing import Callable

from . import winapi as w


class DeviceWatcher:
    """Слушает WM_DEVICECHANGE и вызывает callback из рабочего потока."""

    def __init__(self, on_change: Callable[[], None], debounce: float = 0.35):
        self._on_change = on_change
        self._debounce = debounce
        self._pending = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._consumer: threading.Thread | None = None
        self._hwnd = None
        self._wndproc_ref = None
        self._class_name = f"PortGuardWatcher_{os.getpid()}_{id(self)}"
        self._events: list[int] = []
        self._lock = threading.Lock()
        self._started = False

    # -- публичное API ------------------------------------------------------
    def start(self) -> bool:
        """Запускает поток с окном. Возвращает False, если окно не создалось."""
        if self._thread and self._thread.is_alive():
            return self._started
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._message_loop, name="portguard-hotplug", daemon=True
        )
        self._thread.start()
        # Ждём, пока окно создастся, чтобы честно вернуть результат.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if self._hwnd or not self._thread.is_alive():
                break
            time.sleep(0.02)
        if self._hwnd:
            self._consumer = threading.Thread(
                target=self._consume, name="portguard-hotplug-worker", daemon=True
            )
            self._consumer.start()
        return bool(self._hwnd)

    def stop(self) -> None:
        self._stop.set()
        hwnd = self._hwnd
        if hwnd:
            w.user32.PostMessageW(hwnd, w.WM_CLOSE, 0, 0)
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._consumer:
            self._consumer.join(timeout=1.0)
        self._hwnd = None
        self._started = False

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and self._hwnd)

    def note_change(self, code: int) -> None:
        """Позволяет вручную сообщить об изменении (используется в тестах)."""
        with self._lock:
            self._events.append(code)
        self._pending.set()

    # -- внутреннее ---------------------------------------------------------
    def _consume(self) -> None:
        while not self._stop.is_set():
            if not self._pending.wait(0.5):
                continue
            self._pending.clear()
            time.sleep(self._debounce)  # схлопываем серию событий
            self._pending.clear()
            with self._lock:
                self._events.clear()
            if self._stop.is_set():
                return
            try:
                self._on_change()
            except Exception:
                pass

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == w.WM_DEVICECHANGE:
            self.note_change(int(wparam))
            return 0
        if msg == w.WM_CLOSE:
            w.user32.DestroyWindow(hwnd)
            return 0
        if msg == w.WM_DESTROY:
            w.user32.PostQuitMessage(0)
            return 0
        return w.user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _message_loop(self) -> None:
        instance = w.kernel32.GetModuleHandleW(None)
        self._wndproc_ref = w.WNDPROC(self._wndproc)

        wc = w.WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(w.WNDCLASSEXW)
        wc.style = 0
        wc.lpfnWndProc = ctypes.cast(self._wndproc_ref, ctypes.c_void_p)
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = instance
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = self._class_name
        wc.hIconSm = None

        if not w.user32.RegisterClassExW(ctypes.byref(wc)):
            return
        hwnd = w.user32.CreateWindowExW(
            w.WS_EX_TOOLWINDOW,
            self._class_name,
            "PortGuard device watcher",
            w.WS_POPUP,
            0,
            0,
            0,
            0,
            None,
            None,
            instance,
            None,
        )
        if not hwnd:
            return
        self._hwnd = hwnd
        self._started = True

        msg = w.MSG()
        while not self._stop.is_set():
            result = w.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result == 0 or result == -1:
                break
            w.user32.TranslateMessage(ctypes.byref(msg))
            w.user32.DispatchMessageW(ctypes.byref(msg))
        self._started = False
