"""Окно COM-терминала: чтение, отправка, HEX и сброс платы."""

from __future__ import annotations

import queue
import time
import tkinter as tk

import customtkinter as ctk

from ..core.model import Device
from ..core.serial_monitor import SerialPortError, SerialSession
from . import theme

BAUDRATES = ("9600", "19200", "38400", "57600", "115200", "230400", "460800", "921600")
LINE_ENDINGS = {
    "Без перевода": "none",
    "LF (\\n)": "lf",
    "CR (\\r)": "cr",
    "CRLF (\\r\\n)": "crlf",
}


class SerialMonitorWindow(ctk.CTkToplevel):
    def __init__(self, master, device: Device):
        super().__init__(master)
        self.device = device
        self.port = device.com_port or ""
        self._queue: queue.Queue = queue.Queue()
        self._closed = False
        self._rx = 0
        self._tx = 0

        self.title(f"COM-монитор — {self.port}")
        self.geometry("940x640")
        self.minsize(720, 480)
        self.configure(fg_color=theme.BG)

        self.session = SerialSession(
            self.port,
            115200,
            on_data=lambda data: self._queue.put(("data", data)),
            on_error=lambda text: self._queue.put(("error", text)),
        )

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(60, self._drain)
        self.after(200, self._open)

    # -- интерфейс ----------------------------------------------------------
    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=0, height=58)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        header.grid_propagate(False)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w", padx=16, pady=10)
        ctk.CTkLabel(
            title_box,
            text=self.port,
            font=theme.font(18, "bold"),
            text_color=theme.TEXT,
        ).pack(anchor="w")
        subtitle = self.device.chip_name or self.device.display_name
        ctk.CTkLabel(
            title_box, text=subtitle, font=theme.font(10), text_color=theme.TEXT_MUTED
        ).pack(anchor="w")

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.grid(row=0, column=1, sticky="e", padx=16)

        self.baud_menu = ctk.CTkOptionMenu(
            controls,
            values=list(BAUDRATES),
            width=104,
            height=30,
            font=theme.font(11),
            fg_color=theme.PANEL_ALT,
            button_color=theme.BORDER,
            button_hover_color=theme.TEXT_MUTED,
            command=self._change_baud,
        )
        self.baud_menu.set("115200")
        self.baud_menu.pack(side="left", padx=(0, 8))

        self.open_button = ctk.CTkButton(
            controls,
            text="Открыть",
            width=104,
            height=30,
            font=theme.font(11, "bold"),
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            command=self._toggle_open,
        )
        self.open_button.pack(side="left")

        options = ctk.CTkFrame(self, fg_color=theme.BG_ALT, corner_radius=0)
        options.grid(row=1, column=0, sticky="ew")
        options.grid_columnconfigure(10, weight=1)

        def switch(parent, text, command=None, width=104):
            widget = ctk.CTkSwitch(
                parent,
                text=text,
                font=theme.font(10),
                text_color=theme.TEXT_DIM,
                progress_color=theme.ACCENT,
                width=width,
                command=command,
            )
            return widget

        self.time_var = ctk.BooleanVar(value=True)
        f_time = switch(options, "Время", width=90)
        f_time.configure(variable=self.time_var)
        f_time.grid(row=0, column=0, padx=(14, 8), pady=8, sticky="w")

        self.hex_var = ctk.BooleanVar(value=False)
        f_hex = switch(options, "HEX", width=70)
        f_hex.configure(variable=self.hex_var)
        f_hex.grid(row=0, column=1, padx=6, pady=8, sticky="w")

        self.autoscroll_var = ctk.BooleanVar(value=True)
        f_auto = switch(options, "Автоскролл", width=110)
        f_auto.configure(variable=self.autoscroll_var)
        f_auto.grid(row=0, column=2, padx=6, pady=8, sticky="w")

        self.dtr_var = ctk.BooleanVar(value=True)
        self.f_dtr = switch(options, "DTR", width=64, command=self._toggle_dtr)
        self.f_dtr.configure(variable=self.dtr_var)
        self.f_dtr.grid(row=0, column=3, padx=6, pady=8, sticky="w")

        self.rts_var = ctk.BooleanVar(value=True)
        self.f_rts = switch(options, "RTS", width=64, command=self._toggle_rts)
        self.f_rts.configure(variable=self.rts_var)
        self.f_rts.grid(row=0, column=4, padx=6, pady=8, sticky="w")

        reset_arduino = ctk.CTkButton(
            options,
            text="Сброс Arduino",
            width=116,
            height=27,
            font=theme.font(10),
            fg_color=theme.PANEL_ALT,
            hover_color=theme.BORDER,
            command=self._reset_arduino,
        )
        reset_arduino.grid(row=0, column=5, padx=(12, 4), pady=8)

        esp_boot = ctk.CTkButton(
            options,
            text="ESP: загрузчик",
            width=118,
            height=27,
            font=theme.font(10),
            fg_color=theme.PANEL_ALT,
            hover_color=theme.BORDER,
            command=self._esp_bootloader,
        )
        esp_boot.grid(row=0, column=6, padx=4, pady=8)

        esp_reset = ctk.CTkButton(
            options,
            text="ESP: сброс",
            width=100,
            height=27,
            font=theme.font(10),
            fg_color=theme.PANEL_ALT,
            hover_color=theme.BORDER,
            command=self._esp_reset,
        )
        esp_reset.grid(row=0, column=7, padx=4, pady=8)

        self.clear_button = ctk.CTkButton(
            options,
            text="Очистить",
            width=90,
            height=27,
            font=theme.font(10),
            fg_color="transparent",
            hover_color=theme.PANEL_ALT,
            text_color=theme.TEXT_DIM,
            command=self._clear,
        )
        self.clear_button.grid(row=0, column=9, padx=(4, 14), pady=8)

        console = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=0)
        console.grid(row=2, column=0, sticky="nsew", padx=14, pady=(12, 0))
        console.grid_rowconfigure(0, weight=1)
        console.grid_columnconfigure(0, weight=1)

        self.text = tk.Text(
            console,
            bg=theme.PANEL,
            fg=theme.TEXT,
            insertbackground=theme.ACCENT,
            relief="flat",
            borderwidth=0,
            wrap="char",
            font=(theme.MONO_FAMILY, 10),
            padx=10,
            pady=8,
            state="disabled",
        )
        scrollbar = ctk.CTkScrollbar(
            console,
            orientation="vertical",
            command=self.text.yview,
            fg_color=theme.PANEL,
            button_color=theme.PANEL_ALT,
            button_hover_color=theme.TEXT_MUTED,
            width=12,
        )
        self.text.configure(yscrollcommand=scrollbar.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.text.tag_configure("rx", foreground=theme.TEXT)
        self.text.tag_configure("tx", foreground=theme.ACCENT)
        self.text.tag_configure("err", foreground=theme.ERROR)
        self.text.tag_configure("meta", foreground=theme.TEXT_MUTED)
        self.text.tag_configure("time", foreground=theme.TEXT_MUTED)

        send = ctk.CTkFrame(self, fg_color="transparent")
        send.grid(row=3, column=0, sticky="ew", padx=14, pady=12)
        send.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            send,
            placeholder_text="Сообщение… (Enter — отправить)",
            height=34,
            font=theme.mono(11),
            fg_color=theme.PANEL,
            border_color=theme.BORDER,
        )
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda _e: self._send())

        self.ending_menu = ctk.CTkOptionMenu(
            send,
            values=list(LINE_ENDINGS),
            width=132,
            height=34,
            font=theme.font(10),
            fg_color=theme.PANEL,
            button_color=theme.BORDER,
            button_hover_color=theme.TEXT_MUTED,
        )
        self.ending_menu.set("LF (\\n)")
        self.ending_menu.grid(row=0, column=1, padx=(8, 8))

        self.send_button = ctk.CTkButton(
            send,
            text="Отправить",
            width=112,
            height=34,
            font=theme.font(11, "bold"),
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            command=self._send,
            state="disabled",
        )
        self.send_button.grid(row=0, column=2)

        self.status = ctk.CTkLabel(
            self,
            text="Порт закрыт",
            font=theme.font(9),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        )
        self.status.grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 8))

    # -- открытие/закрытие --------------------------------------------------
    def _open(self) -> None:
        try:
            self.session.open()
        except SerialPortError as exc:
            self._append_meta(f"Не удалось открыть: {exc}")
            self._set_state(False, str(exc))
            return
        self.session.start_reader()
        self._set_state(True)
        self._append_meta(f"Открыт {self.port} @ {self.session.baudrate}")
        self.dtr_var.set(True)
        self.rts_var.set(True)

    def _toggle_open(self) -> None:
        if self.session.is_open:
            self.session.close()
            self._set_state(False, "Порт закрыт")
            self._append_meta("Порт закрыт")
        else:
            self._open()

    def _set_state(self, opened: bool, message: str = "") -> None:
        self.open_button.configure(text="Закрыть" if opened else "Открыть")
        self.send_button.configure(state="normal" if opened else "disabled")
        if opened:
            self.status.configure(
                text=f"Открыт · {self.port} · {self.session.baudrate} бод",
                text_color=theme.OK,
            )
        else:
            self.status.configure(text=message or "Порт закрыт", text_color=theme.TEXT_MUTED)

    def _change_baud(self, value: str) -> None:
        baud = int(value)
        try:
            self.session.set_baudrate(baud)
        except Exception as exc:
            self._append_meta(f"Не удалось сменить скорость: {exc}")
            return
        if self.session.is_open:
            self._append_meta(f"Скорость: {baud}")

    # -- обмен --------------------------------------------------------------
    def _send(self) -> None:
        text = self.entry.get()
        if not text or not self.session.is_open:
            return
        ending_key = LINE_ENDINGS.get(self.ending_menu.get(), "lf")
        hex_mode = bool(self.hex_var.get())
        try:
            sent = self.session.send_text(text, ending_key, as_hex=hex_mode)
        except SerialPortError as exc:
            self._append("err", f"{exc}\n")
            return
        self._tx += sent
        payload = f"[hex] {text}" if hex_mode else text
        self._append("tx", f"{payload}\n")
        self.entry.delete(0, "end")
        self._update_counters()

    def _on_data(self, data: bytes) -> None:
        if self.hex_var.get():
            payload = data.hex(" ").upper() + "\n"
        else:
            payload = data.decode("utf-8", "replace")
        if self.time_var.get() and getattr(self, "_at_line_start", True):
            stamp = time.strftime("%H:%M:%S")
            self._append("time", f"{stamp} ")
        self._append("rx", payload)
        self._at_line_start = payload.endswith("\n")
        self._rx += len(data)
        self._update_counters()

    def _update_counters(self) -> None:
        if self.session.is_open:
            self.status.configure(
                text=(
                    f"Открыт · {self.port} · {self.session.baudrate} бод   "
                    f"RX {_human(self._rx)}   TX {_human(self._tx)}"
                ),
                text_color=theme.OK,
            )

    # -- сброс --------------------------------------------------------------
    def _reset_arduino(self) -> None:
        if not self.session.is_open:
            return
        self.session.pulse_dtr()
        self._append_meta("DTR-импульс: Arduino перезапущен")

    def _esp_bootloader(self) -> None:
        if not self.session.is_open:
            return
        self.session.esp_bootloader()
        self._append_meta("ESP32 переведён в режим загрузчика")

    def _esp_reset(self) -> None:
        if not self.session.is_open:
            return
        self.session.esp_reset()
        self._append_meta("ESP32 перезапущен (RTS)")

    def _toggle_dtr(self) -> None:
        if self.session.is_open:
            self.session.set_dtr(bool(self.dtr_var.get()))

    def _toggle_rts(self) -> None:
        if self.session.is_open:
            self.session.set_rts(bool(self.rts_var.get()))

    # -- вывод --------------------------------------------------------------
    def _append(self, tag: str, text: str) -> None:
        self.text.configure(state="normal")
        self.text.insert("end", text, tag)
        if self.autoscroll_var.get():
            self.text.see("end")
        self.text.configure(state="disabled")

    def _append_meta(self, text: str) -> None:
        self._append("meta", f"— {text} —\n")

    def _clear(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
        self._rx = self._tx = 0
        self._update_counters()

    # -- цикл ---------------------------------------------------------------
    def _drain(self) -> None:
        if self._closed:
            return
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                if kind == "data":
                    self._on_data(payload)
                elif kind == "error":
                    self._append("err", f"\n[ошибка] {payload}\n")
                    self._set_state(False, f"Ошибка: {payload}")
        except queue.Empty:
            pass
        self.after(60, self._drain)

    def _on_close(self) -> None:
        self._closed = True
        try:
            self.session.close()
        finally:
            self.destroy()


def _human(size: int) -> str:
    if size < 1024:
        return f"{size} Б"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} КБ"
    return f"{size / (1024 * 1024):.2f} МБ"
