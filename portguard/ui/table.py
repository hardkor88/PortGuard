"""Таблица устройств на ttk.Treeview, оформленная под тёмную тему.

Treeview выбран осознанно: на 200+ строк он быстрее и предсказуемее, чем
двести отдельных виджетов customtkinter, и нормально переживает частые
обновления при hot-plug.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable

import customtkinter as ctk

from ..core.model import Device, sort_key
from . import theme

COLUMNS = (
    ("port", "Порт", 62, "center"),
    ("name", "Устройство", 300, "w"),
    ("class", "Класс", 140, "w"),
    ("vidpid", "VID:PID", 104, "center"),
    ("status", "Состояние", 128, "w"),
)


class DeviceTable(ctk.CTkFrame):
    def __init__(
        self,
        master,
        on_select: Callable[[str | None], None],
        on_activate: Callable[[str], None] | None = None,
    ):
        super().__init__(master, fg_color=theme.PANEL, corner_radius=0)
        self._on_select = on_select
        self._on_activate = on_activate
        self._devices: list[Device] = []
        self._order: tuple[str, bool] | None = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "PG.Treeview",
            background=theme.PANEL,
            fieldbackground=theme.PANEL,
            foreground=theme.TEXT,
            borderwidth=0,
            rowheight=31,
            font=(theme.FONT_FAMILY, 10),
        )
        style.configure(
            "PG.Treeview.Heading",
            background=theme.BG_ALT,
            foreground=theme.TEXT_DIM,
            relief="flat",
            borderwidth=0,
            font=(theme.FONT_FAMILY, 9, "bold"),
            padding=(10, 7),
        )
        style.map(
            "PG.Treeview.Heading",
            background=[("active", theme.PANEL_ALT)],
            foreground=[("active", theme.TEXT)],
        )
        style.map(
            "PG.Treeview",
            background=[("selected", theme.ACCENT_SOFT)],
            foreground=[("selected", theme.TEXT)],
        )
        style.layout("PG.Treeview", [("PG.Treeview.treearea", {"sticky": "nswe"})])

        column_ids = [column[0] for column in COLUMNS]
        self.tree = ttk.Treeview(
            self,
            columns=column_ids,
            show="headings",
            style="PG.Treeview",
            selectmode="browse",
        )
        for key, title, width, anchor in COLUMNS:
            self.tree.heading(
                key, text=title, anchor=anchor, command=lambda k=key: self._sort_by(k)
            )
            self.tree.column(key, width=width, anchor=anchor, stretch=(key == "name"))

        self.tree.tag_configure("alt", background=theme.PANEL_ALT)
        self.tree.tag_configure("err", foreground=theme.ERROR)
        self.tree.tag_configure("off", foreground=theme.TEXT_MUTED)
        self.tree.tag_configure("port", foreground=theme.ACCENT)
        self.tree.tag_configure("warn", foreground=theme.WARN)

        scrollbar = ctk.CTkScrollbar(
            self,
            orientation="vertical",
            command=self.tree.yview,
            fg_color=theme.PANEL,
            button_color=theme.PANEL_ALT,
            button_hover_color=theme.TEXT_MUTED,
            width=12,
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.empty_label = ctk.CTkLabel(
            self,
            text="Ничего не найдено",
            text_color=theme.TEXT_MUTED,
            font=theme.font(12),
        )

        self.tree.bind("<<TreeviewSelect>>", self._handle_select)
        self.tree.bind("<Double-1>", self._handle_activate)

    # -- данные -------------------------------------------------------------
    def set_devices(self, devices: Iterable[Device], keep_id: str | None = None) -> None:
        self._devices = list(devices)
        rows = self._sorted(self._devices)

        if self._order is None:
            rows.sort(key=sort_key)

        self.tree.delete(*self.tree.get_children())
        for index, device in enumerate(rows):
            tags: list[str] = []
            if index % 2:
                tags.append("alt")
            tags.append(self._tag_for(device))
            self.tree.insert(
                "",
                "end",
                iid=device.instance_id,
                values=(
                    device.com_port or "—",
                    device.display_name,
                    device.device_class or "—",
                    device.vid_pid_text or "—",
                    " " + device.short_status,
                ),
                tags=tuple(tags),
            )

        if not rows:
            self.empty_label.place(relx=0.5, rely=0.45, anchor="center")
        else:
            self.empty_label.place_forget()

        if keep_id and self.tree.exists(keep_id):
            self.tree.selection_set(keep_id)
            self.tree.see(keep_id)
        else:
            self._on_select(None)

    @staticmethod
    def _tag_for(device: Device) -> str:
        if device.status_kind in ("error",):
            return "err"
        if device.status_kind in ("disabled", "absent"):
            return "off"
        if device.status_kind == "stopped":
            return "warn"
        if device.com_port:
            return "port"
        return ""

    def _sorted(self, devices: list[Device]) -> list[Device]:
        if self._order is None:
            return list(devices)
        key, reverse = self._order
        getters = {
            "port": lambda d: (d.com_port is None, d.com_port or ""),
            "name": lambda d: d.display_name.casefold(),
            "class": lambda d: (d.device_class or "").casefold(),
            "vidpid": lambda d: d.vid_pid_text,
            "status": lambda d: d.status_text.casefold(),
        }
        return sorted(devices, key=getters.get(key, getters["name"]), reverse=reverse)

    def _sort_by(self, key: str) -> None:
        if self._order and self._order[0] == key:
            self._order = (key, not self._order[1])
        else:
            self._order = (key, False)
        for column_key, title, _, _ in COLUMNS:
            arrow = ""
            if self._order and self._order[0] == column_key:
                arrow = " ↓" if self._order[1] else " ↑"
            self.tree.heading(column_key, text=title + arrow)
        keep = self.selected_id
        self.set_devices(self._devices, keep_id=keep)

    # -- выбор --------------------------------------------------------------
    @property
    def selected_id(self) -> str | None:
        selection = self.tree.selection()
        return selection[0] if selection else None

    def select(self, instance_id: str | None) -> None:
        if instance_id and self.tree.exists(instance_id):
            self.tree.selection_set(instance_id)
            self.tree.see(instance_id)

    def _handle_select(self, _event=None) -> None:
        self._on_select(self.selected_id)

    def _handle_activate(self, _event=None) -> None:
        if self._on_activate and self.selected_id:
            self._on_activate(self.selected_id)
