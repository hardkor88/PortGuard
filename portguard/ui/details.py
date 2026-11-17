"""Правая панель: подробности о выбранном устройстве и действия."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core.model import Device
from ..core.holders import HolderReport
from . import theme

FIELDS = (
    ("COM-порт", "com_port"),
    ("VID:PID", "vid_pid"),
    ("Чип / плата", "chip"),
    ("Класс", "device_class"),
    ("Производитель", "manufacturer"),
    ("Драйвер", "driver_version"),
    ("Расположение", "location"),
    ("Шина", "enumerator"),
    ("Держит порт", "held_by"),
    ("Instance ID", "instance_id"),
    ("Hardware ID", "hardware_id"),
)


class DetailsPanel(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_toggle: Callable[[], None],
        on_restart: Callable[[], None],
        on_eject: Callable[[], None],
        on_monitor: Callable[[], None],
        on_holders: Callable[[], None],
        on_copy: Callable[[], None],
        on_devmgmt: Callable[[], None],
        admin: bool = False,
    ):
        super().__init__(master, fg_color=theme.PANEL, corner_radius=0, width=352)
        self.grid_propagate(False)
        self._device: Device | None = None
        self._admin = admin
        self._callbacks = {
            "toggle": on_toggle,
            "restart": on_restart,
            "eject": on_eject,
            "monitor": on_monitor,
            "holders": on_holders,
            "copy": on_copy,
            "devmgmt": on_devmgmt,
        }
        self._values: dict[str, ctk.CTkLabel] = {}

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_fields()
        self._build_actions()
        self.show(None)
    # -- построение ---------------------------------------------------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        header.grid_columnconfigure(0, weight=1)

        self.name_label = ctk.CTkLabel(
            header,
            text="Устройство не выбрано",
            font=theme.font(16, "bold"),
            text_color=theme.TEXT,
            anchor="w",
            justify="left",
            wraplength=310,
        )
        self.name_label.grid(row=0, column=0, sticky="w")

        self.subtitle_label = ctk.CTkLabel(
            header,
            text="Выберите строку в списке слева",
            font=theme.font(11),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=310,
        )
        self.subtitle_label.grid(row=1, column=0, sticky="w", pady=(3, 0))

        self.badge = ctk.CTkLabel(
            header,
            text="—",
            font=theme.font(10, "bold"),
            text_color="#ffffff",
            fg_color=theme.TEXT_MUTED,
            corner_radius=6,
            padx=10,
            pady=3,
        )
        self.badge.grid(row=2, column=0, sticky="w", pady=(9, 0))

        separator = ctk.CTkFrame(self, height=1, fg_color=theme.BORDER)
        separator.grid(row=1, column=0, sticky="ew")

    def _build_fields(self) -> None:
        self.fields_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.TEXT_MUTED,
        )
        self.fields_frame.grid(row=2, column=0, sticky="nsew", padx=(10, 4), pady=4)
        self.fields_frame.grid_columnconfigure(0, weight=1)

        for index, (title, key) in enumerate(FIELDS):
            row = ctk.CTkFrame(self.fields_frame, fg_color="transparent")
            row.grid(row=index, column=0, sticky="ew", pady=(0, 9))
            row.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                row,
                text=title.upper(),
                font=theme.font(9, "bold"),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")

            value = ctk.CTkLabel(
                row,
                text="—",
                font=theme.mono(10) if key in ("instance_id", "hardware_id") else theme.font(11),
                text_color=theme.TEXT_DIM,
                anchor="w",
                justify="left",
                wraplength=300,
            )
            value.grid(row=1, column=0, sticky="w", pady=(2, 0))
            self._values[key] = value

        self.placeholder = ctk.CTkLabel(
            self,
            text="Выберите устройство,\nчтобы увидеть детали\nи доступные действия",
            font=theme.font(11),
            text_color=theme.TEXT_MUTED,
            justify="center",
        )

    def _build_actions(self) -> None:
        wrapper = ctk.CTkFrame(self, fg_color="transparent")
        wrapper.grid(row=3, column=0, sticky="ew", padx=16, pady=(6, 14))
        wrapper.grid_columnconfigure((0, 1), weight=1)
        self.actions_wrapper = wrapper

        def button(text: str, key: str, row: int, column: int, accent: bool = False):
            widget = ctk.CTkButton(
                wrapper,
                text=text,
                height=31,
                corner_radius=7,
                font=theme.font(11),
                fg_color=theme.ACCENT if accent else theme.PANEL_ALT,
                hover_color=theme.ACCENT_HOVER if accent else theme.BORDER,
                text_color="#ffffff" if accent else theme.TEXT,
                command=self._callbacks[key],
            )
            widget.grid(row=row, column=column, sticky="ew", padx=(0, 6) if column == 0 else (6, 0), pady=4)
            return widget

        self.btn_toggle = button("Отключить", "toggle", 0, 0, accent=True)
        self.btn_restart = button("Перезапустить", "restart", 0, 1)
        self.btn_eject = button("Извлечь", "eject", 1, 0)
        self.btn_monitor = button("Монитор COM", "monitor", 1, 1)
        self.btn_holders = button("Кто занял порт", "holders", 2, 0)
        self.btn_copy = button("Копировать ID", "copy", 2, 1)

        self.btn_devmgmt = ctk.CTkButton(
            wrapper,
            text="Диспетчер устройств Windows",
            height=29,
            corner_radius=7,
            font=theme.font(11),
            fg_color="transparent",
            hover_color=theme.PANEL_ALT,
            border_width=1,
            border_color=theme.BORDER,
            text_color=theme.TEXT_DIM,
            command=self._callbacks["devmgmt"],
        )
        self.btn_devmgmt.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        self.hint = ctk.CTkLabel(
            wrapper,
            text="",
            font=theme.font(9),
            text_color=theme.TEXT_MUTED,
            anchor="w",
            justify="left",
            wraplength=310,
        )
        self.hint.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))

    # -- обновление ---------------------------------------------------------
    def show(self, device: Device | None, busy: HolderReport | None = None) -> None:
        self._device = device
        if device is None:
            self.name_label.configure(text="Устройство не выбрано")
            self.subtitle_label.configure(text="Выберите строку в списке слева")
            self.badge.configure(text="—", fg_color=theme.PANEL_ALT, text_color=theme.TEXT_MUTED)
            self.fields_frame.grid_remove()
            self.actions_wrapper.grid_remove()
            self.placeholder.grid(row=2, column=0, sticky="nsew")
            return

        self.placeholder.grid_remove()
        self.fields_frame.grid()
        self.actions_wrapper.grid()
        self.name_label.configure(text=device.display_name)
        subtitle = device.chip_name or device.vendor_name or device.device_class
        self.subtitle_label.configure(text=subtitle or "—")
        color = theme.STATUS_COLORS.get(device.status_kind, theme.TEXT_MUTED)
        self.badge.configure(text=device.status_text, fg_color=color, text_color="#ffffff")

        values = {
            "com_port": device.com_port or "—",
            "vid_pid": device.vid_pid_text or "—",
            "chip": device.chip_name or "—",
            "device_class": device.device_class or "—",
            "manufacturer": device.manufacturer or "—",
            "driver_version": device.driver_version or "—",
            "location": device.location or "—",
            "enumerator": device.enumerator or "—",
            "held_by": self._held_by_text(busy),
            "instance_id": device.instance_id,
            "hardware_id": device.hardware_ids[0] if device.hardware_ids else "—",
        }
        for key, text in values.items():
            self._values[key].configure(text=text)

        self._set_actions_enabled(True)
        self._update_buttons(device)

    def update_busy(self, busy: HolderReport | None) -> None:
        self._values["held_by"].configure(text=self._held_by_text(busy))

    @staticmethod
    def _held_by_text(busy: HolderReport | None) -> str:
        if busy is None:
            return "не проверялось"
        if busy.error:
            if busy.needs_admin:
                return "нужны права администратора"
            return busy.error
        if not busy.holders:
            return "никто не держит"
        return ", ".join(f"{holder.name} (PID {holder.pid})" for holder in busy.holders)

    def _style(self, button: ctk.CTkButton, enabled: bool, accent: bool = False) -> None:
        """Включает/выключает кнопку и приводит её вид в соответствие."""
        button.configure(
            state="normal" if enabled else "disabled",
            fg_color=(theme.ACCENT if accent else theme.PANEL_ALT)
            if enabled
            else theme.PANEL,
            text_color=("#ffffff" if accent else theme.TEXT)
            if enabled
            else theme.TEXT_MUTED,
            border_width=0 if accent else 1,
            border_color=theme.BORDER if enabled else theme.PANEL,
        )

    def _set_actions_enabled(self, enabled: bool) -> None:
        for widget in (
            self.btn_toggle,
            self.btn_restart,
            self.btn_eject,
            self.btn_monitor,
            self.btn_holders,
            self.btn_copy,
        ):
            self._style(widget, enabled)
        self.btn_devmgmt.configure(state="normal")

    def _update_buttons(self, device: Device) -> None:
        disabled = device.status_kind == "disabled"
        self.btn_toggle.configure(text="Включить" if disabled else "Отключить")

        needs_admin = not self._admin
        self._style(self.btn_toggle, not needs_admin and device.disableable, accent=True)
        self._style(self.btn_restart, not needs_admin)
        self._style(self.btn_eject, not needs_admin and device.removable)
        self._style(self.btn_monitor, bool(device.com_port))
        self._style(self.btn_holders, bool(device.com_port))
        self._style(self.btn_copy, True)

        if needs_admin:
            self.hint.configure(
                text="Переключение, перезапуск и извлечение требуют прав администратора."
            )
        elif device.com_port:
            self.hint.configure(text="Монитор COM откроет порт: Arduino/ESP при этом перезапустятся.")
        else:
            self.hint.configure(text="")
