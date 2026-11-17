"""Главное окно PortGuard."""

from __future__ import annotations

import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .. import __version__
from ..core import setupapi
from ..core.elevation import is_admin, relaunch_as_admin
from ..core.holders import HolderReport, find_port_holders
from ..core.hotplug import DeviceWatcher
from ..core.model import CATEGORIES, Device, summary
from ..core.report import save_report, summary_text
from . import theme
from .details import DetailsPanel
from .monitor_window import SerialMonitorWindow
from .table import DeviceTable

REFRESH_INTERVAL = 5000  # страховочный опрос, если hot-plug недоступен


def _resource_path(relative: str) -> str:
    """Путь к ресурсу и в исходниках, и внутри собранного PyInstaller exe."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, relative)
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(root, relative)


def _enable_dpi_awareness() -> None:
    """
    Включает DPI-awareness до создания окна.

    customtkinter сам масштабирует виджеты под DPI, но если процесс остаётся
    DPI-unaware, Tk видит виртуальный экран (1707×960 вместо 2560×1440) и окно
    с учётом масштаба уезжает за край. Поэтому сообщаем Windows о DPI заранее.
    """
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class PortGuardApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"PortGuard {__version__} — устройства Windows")
        self._fit_to_screen()
        self.configure(fg_color=theme.BG)
        self._set_window_icon()

        self.devices: list[Device] = []
        self.by_id: dict[str, Device] = {}
        self.busy_reports: dict[str, HolderReport] = {}
        self.selected_id: str | None = None
        self.category = "all"
        self.only_problems = False
        self.search_text = ""
        self.admin = is_admin()
        self._queue: queue.Queue = queue.Queue()
        self._search_job: str | None = None
        self._refresh_pending = False
        self._watcher: DeviceWatcher | None = None
        self._poll_job: str | None = None
        self._monitors: list[SerialMonitorWindow] = []
        self._log_visible = True
        self._category_buttons: dict[str, ctk.CTkButton] = {}

        self._build_topbar()
        self._build_sidebar()
        self._build_body()
        self._build_statusbar()
        self._set_category("all")

        self.bind("<F5>", lambda _e: self.refresh_async())
        self.bind("<Control-f>", lambda _e: self.search_entry.focus_set())
        self.bind("<Escape>", lambda _e: self._clear_search())

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(80, self._drain_queue)
        self.after(200, self.refresh_async)
        self._start_watcher()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------
    def _set_window_icon(self) -> None:
        try:
            icon = _resource_path(os.path.join("assets", "icon.ico"))
            if os.path.exists(icon):
                self.iconbitmap(icon)
        except Exception:
            pass

    def _fit_to_screen(self) -> None:
        """Подбирает размер окна под экран с учётом масштаба Windows."""
        try:
            scale = self._apply_window_scaling(100) / 100
        except Exception:
            scale = 1.0
        screen_w = int(self.winfo_screenwidth() / scale)
        screen_h = int(self.winfo_screenheight() / scale)
        width = max(900, min(1360, screen_w - 40))
        height = max(620, min(860, screen_h - 70))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.minsize(min(980, width), min(620, height))

    def _build_topbar(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=0, height=62)
        top.grid(row=0, column=0, columnspan=2, sticky="ew")
        top.grid_propagate(False)
        top.grid_columnconfigure(1, weight=1)

        brand = ctk.CTkFrame(top, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="w", padx=(16, 24), pady=10)

        mark = ctk.CTkFrame(brand, width=10, height=26, corner_radius=3, fg_color=theme.ACCENT)
        mark.pack(side="left", padx=(0, 8))

        titles = ctk.CTkFrame(brand, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(
            titles, text="PortGuard", font=theme.font(17, "bold"), text_color=theme.TEXT
        ).pack(anchor="w")
        ctk.CTkLabel(
            titles,
            text="все подключённые устройства",
            font=theme.font(9),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w")

        search_wrap = ctk.CTkFrame(top, fg_color="transparent")
        search_wrap.grid(row=0, column=1, sticky="ew", padx=(0, 16), pady=12)
        search_wrap.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            search_wrap,
            placeholder_text="Поиск: имя, COM3, VID:PID, instance id…",
            height=34,
            font=theme.font(11),
            fg_color=theme.BG_ALT,
            border_color=theme.BORDER,
        )
        self.search_entry.grid(row=0, column=0, sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        actions = ctk.CTkFrame(top, fg_color="transparent")
        actions.grid(row=0, column=2, sticky="e", padx=(0, 16), pady=12)

        self.problems_switch = ctk.CTkSwitch(
            actions,
            text="Только с проблемами",
            font=theme.font(10),
            text_color=theme.TEXT_DIM,
            progress_color=theme.ACCENT,
            command=self._on_problems_toggle,
        )
        self.problems_switch.pack(side="left", padx=(0, 14))

        def toolbar_button(text: str, command, width: int = 104):
            return ctk.CTkButton(
                actions,
                text=text,
                width=width,
                height=32,
                font=theme.font(10),
                fg_color=theme.PANEL_ALT,
                hover_color=theme.BORDER,
                text_color=theme.TEXT,
                command=command,
            )

        self.refresh_button = toolbar_button("Обновить", self.refresh_async)
        self.refresh_button.pack(side="left", padx=4)

        self.scan_button = toolbar_button("Занятость портов", self._scan_ports, 132)
        self.scan_button.pack(side="left", padx=4)

        self.export_button = toolbar_button("Отчёт", self._export_report, 82)
        self.export_button.pack(side="left", padx=4)

    def _build_sidebar(self) -> None:
        sidebar = ctk.CTkFrame(self, fg_color=theme.BG_ALT, corner_radius=0, width=232)
        sidebar.grid(row=1, column=0, sticky="nsw")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(1, weight=1)
        sidebar.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            sidebar,
            text="КАТЕГОРИИ",
            font=theme.font(9, "bold"),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 6))

        container = ctk.CTkScrollableFrame(
            sidebar,
            fg_color="transparent",
            scrollbar_button_color=theme.BORDER,
            scrollbar_button_hover_color=theme.TEXT_MUTED,
        )
        container.grid(row=1, column=0, sticky="nsew", padx=(8, 4))
        container.grid_columnconfigure(0, weight=1)

        for index, (key, title) in enumerate(CATEGORIES):
            button = ctk.CTkButton(
                container,
                text=title,
                anchor="w",
                height=32,
                corner_radius=7,
                font=theme.font(11),
                fg_color="transparent",
                hover_color=theme.PANEL,
                text_color=theme.TEXT_DIM,
                command=lambda k=key: self._set_category(k),
            )
            button.grid(row=index, column=0, sticky="ew", pady=1)
            self._category_buttons[key] = button

        footer = ctk.CTkFrame(sidebar, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=14, pady=12)
        self.log_button = ctk.CTkButton(
            footer,
            text="Скрыть журнал",
            height=28,
            font=theme.font(10),
            fg_color="transparent",
            hover_color=theme.PANEL,
            border_width=1,
            border_color=theme.BORDER,
            text_color=theme.TEXT_DIM,
            command=self._toggle_log,
        )
        self.log_button.pack(fill="x")

    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        body.grid(row=1, column=1, sticky="nsew")
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self.table = DeviceTable(
            body,
            on_select=self._on_select,
            on_activate=self._on_row_activate,
        )
        self.table.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=12)

        self.details = DetailsPanel(
            body,
            on_toggle=self._toggle_device,
            on_restart=self._restart_device,
            on_eject=self._eject_device,
            on_monitor=lambda: self._open_monitor(self.selected_id),
            on_holders=self._who_holds_selected,
            on_copy=self._copy_selected_id,
            on_devmgmt=self._open_devmgmt,
            admin=self.admin,
        )
        self.details.grid(row=0, column=1, sticky="nse", padx=(8, 0), pady=12)

        log_frame = ctk.CTkFrame(body, fg_color=theme.PANEL, corner_radius=0, height=150)
        log_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(12, 0), pady=(0, 12))
        log_frame.grid_propagate(False)
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(log_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(8, 2))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="ЖУРНАЛ СОБЫТИЙ",
            font=theme.font(9, "bold"),
            text_color=theme.TEXT_MUTED,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(
            header,
            text="Очистить",
            width=76,
            height=22,
            font=theme.font(9),
            fg_color="transparent",
            hover_color=theme.PANEL_ALT,
            text_color=theme.TEXT_MUTED,
            command=self._clear_log,
        ).grid(row=0, column=1, sticky="e")

        self.log_text = tk.Text(
            log_frame,
            bg=theme.PANEL,
            fg=theme.TEXT_DIM,
            relief="flat",
            borderwidth=0,
            height=6,
            wrap="none",
            font=(theme.MONO_FAMILY, 9),
            padx=12,
            pady=2,
            state="disabled",
        )
        self.log_text.grid(row=1, column=0, sticky="nsew", padx=(12, 4), pady=(0, 8))
        log_scroll = ctk.CTkScrollbar(
            log_frame,
            orientation="vertical",
            command=self.log_text.yview,
            fg_color=theme.PANEL,
            button_color=theme.PANEL_ALT,
            button_hover_color=theme.TEXT_MUTED,
            width=10,
        )
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.grid(row=1, column=1, sticky="ns", padx=(0, 10), pady=(0, 8))
        self.log_text.tag_configure("add", foreground=theme.OK)
        self.log_text.tag_configure("remove", foreground=theme.ERROR)
        self.log_text.tag_configure("info", foreground=theme.TEXT_DIM)
        self.log_text.tag_configure("warn", foreground=theme.WARN)
        self.log_text.tag_configure("time", foreground=theme.TEXT_MUTED)

        self._log_frame = log_frame

    def _build_statusbar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.BG_ALT, corner_radius=0, height=30)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew")
        bar.grid_propagate(False)
        bar.grid_columnconfigure(1, weight=1)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w", padx=12)

        self.admin_label = ctk.CTkLabel(
            left,
            text="Администратор" if self.admin else "Обычные права",
            font=theme.font(9, "bold"),
            text_color=theme.OK if self.admin else theme.WARN,
        )
        self.admin_label.pack(side="left", padx=(0, 8))

        if not self.admin:
            self.elevate_button = ctk.CTkButton(
                left,
                text="Повысить права",
                width=104,
                height=20,
                font=theme.font(9),
                fg_color="transparent",
                hover_color=theme.PANEL_ALT,
                border_width=1,
                border_color=theme.BORDER,
                text_color=theme.TEXT_DIM,
                command=self._elevate,
            )
            self.elevate_button.pack(side="left")

        self.counts_label = ctk.CTkLabel(
            bar,
            text="",
            font=theme.font(9),
            text_color=theme.TEXT_MUTED,
            anchor="center",
        )
        self.counts_label.grid(row=0, column=1, sticky="ew")

        self.updated_label = ctk.CTkLabel(
            bar,
            text="",
            font=theme.font(9),
            text_color=theme.TEXT_MUTED,
        )
        self.updated_label.grid(row=0, column=2, sticky="e", padx=12)

    # ------------------------------------------------------------------
    # Данные
    # ------------------------------------------------------------------
    def refresh_async(self, quiet: bool = False) -> None:
        if self._refresh_pending:
            return
        self._refresh_pending = True
        self.refresh_button.configure(text="Обновление…", state="disabled")

        def work() -> None:
            try:
                devices = setupapi.enumerate_devices()
            except Exception as exc:  # noqa: BLE001 - показываем пользователю
                self._queue.put(("error", f"Не удалось получить список устройств: {exc}"))
                return
            self._queue.put(("devices", devices, quiet))

        threading.Thread(target=work, name="portguard-refresh", daemon=True).start()

    def _apply_devices(self, devices: list[Device], quiet: bool) -> None:
        old = self.by_id
        new = {device.instance_id: device for device in devices}

        added = [device for key, device in new.items() if key not in old]
        removed = [device for key, device in old.items() if key not in new]
        if old:
            for device in added:
                suffix = f" · {device.com_port}" if device.com_port else ""
                self._log(f"+ {device.display_name}{suffix}", "add")
            for device in removed:
                self._log(f"− {device.display_name}", "remove")

        self.devices = devices
        self.by_id = new
        self._refresh_pending = False
        self.refresh_button.configure(text="Обновить", state="normal")

        if not quiet:
            self._log(f"Обновлено: {len(devices)} устройств", "info")

        ports = {device.com_port for device in devices if device.com_port}
        self.busy_reports = {
            port: report for port, report in self.busy_reports.items() if port in ports
        }

        self._update_counts()
        self._apply_filter()
        self.updated_label.configure(text=f"Обновлено {time.strftime('%H:%M:%S')}")
        if not self._watcher:
            self._schedule_poll()

    def _update_counts(self) -> None:
        counts = summary(self.devices)
        for key, button in self._category_buttons.items():
            value = counts.get(key, 0)
            title = dict(CATEGORIES)[key]
            button.configure(text=f"{title}   {value}")

        ports = counts.get("ports", 0)
        self.counts_label.configure(
            text=(
                f"Устройств: {counts['all']}   ·   COM-портов: {ports}   ·   "
                f"с проблемами: {counts['problem']}"
            )
        )

    def _visible_devices(self) -> list[Device]:
        devices = self.devices
        if self.category == "problem":
            devices = [device for device in devices if device.has_problem]
        elif self.category != "all":
            devices = [device for device in devices if device.category == self.category]
        if self.only_problems and self.category != "problem":
            devices = [device for device in devices if device.has_problem]
        needle = self.search_text.strip().casefold()
        if needle:
            devices = [
                device
                for device in devices
                if needle in device.display_name.casefold()
                or needle in device.instance_id.casefold()
                or needle in (device.com_port or "").casefold()
                or needle in device.vid_pid_text.casefold()
                or needle in device.chip_name.casefold()
                or needle in device.manufacturer.casefold()
                or needle in device.device_class.casefold()
            ]
        return devices

    def _apply_filter(self) -> None:
        visible = self._visible_devices()
        keep = self.selected_id
        self.table.set_devices(visible, keep_id=keep)
        if keep and keep in self.by_id:
            self._on_select(keep)
        elif not self.table.selected_id:
            self.details.show(None)

    # ------------------------------------------------------------------
    # Фильтры и поиск
    # ------------------------------------------------------------------
    def _set_category(self, key: str) -> None:
        self.category = key
        for name, button in self._category_buttons.items():
            if name == key:
                button.configure(fg_color=theme.ACCENT_SOFT, text_color=theme.TEXT)
            else:
                button.configure(fg_color="transparent", text_color=theme.TEXT_DIM)
        self._apply_filter()

    def _on_problems_toggle(self) -> None:
        self.only_problems = bool(self.problems_switch.get())
        self._apply_filter()

    def _on_search_key(self, _event=None) -> None:
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(220, self._commit_search)

    def _commit_search(self) -> None:
        self._search_job = None
        text = self.search_entry.get()
        if text != self.search_text:
            self.search_text = text
            self._apply_filter()

    def _clear_search(self) -> None:
        self.search_entry.delete(0, "end")
        self.search_text = ""
        self._apply_filter()

    # ------------------------------------------------------------------
    # Выбор и действия
    # ------------------------------------------------------------------
    def _on_select(self, instance_id: str | None) -> None:
        self.selected_id = instance_id
        device = self.by_id.get(instance_id) if instance_id else None
        busy = self.busy_reports.get(device.com_port) if device and device.com_port else None
        self.details.show(device, busy)

    def _on_row_activate(self, instance_id: str) -> None:
        device = self.by_id.get(instance_id)
        if device and device.com_port:
            self._open_monitor(instance_id)

    def _current(self) -> Device | None:
        return self.by_id.get(self.selected_id) if self.selected_id else None

    def _toggle_device(self) -> None:
        device = self._current()
        if not device:
            return
        if not self.admin:
            self._offer_elevation("Переключение устройств требует прав администратора.")
            return
        disable = device.status_kind != "disabled"
        action = "отключить" if disable else "включить"
        if disable and not messagebox.askyesno(
            "Отключить устройство?",
            f"Устройство «{device.display_name}» перестанет работать, пока его не включат снова.\n\n"
            "Продолжить?",
            icon="warning",
        ):
            return
        self._log(f"Запрос: {action} «{device.display_name}»", "info")

        def work() -> None:
            result = setupapi.set_device_enabled(device.instance_id, not disable)
            self._queue.put(("action", result))

        threading.Thread(target=work, daemon=True).start()

    def _restart_device(self) -> None:
        device = self._current()
        if not device:
            return
        if not self.admin:
            self._offer_elevation("Перезапуск устройства требует прав администратора.")
            return
        self._log(f"Запрос: перезапуск «{device.display_name}»", "info")

        def work() -> None:
            self._queue.put(("action", setupapi.restart_device(device.instance_id)))

        threading.Thread(target=work, daemon=True).start()

    def _eject_device(self) -> None:
        device = self._current()
        if not device:
            return
        if not self.admin:
            self._offer_elevation("Безопасное извлечение требует прав администратора.")
            return
        if not messagebox.askyesno(
            "Извлечь устройство?",
            f"«{device.display_name}» будет безопасно отключено.\n\n"
            "Убедитесь, что не идёт запись данных.",
            icon="warning",
        ):
            return
        self._log(f"Запрос: извлечение «{device.display_name}»", "info")

        def work() -> None:
            self._queue.put(("action", setupapi.eject_device(device.instance_id)))

        threading.Thread(target=work, daemon=True).start()

    def _open_monitor(self, instance_id: str | None) -> None:
        device = self.by_id.get(instance_id) if instance_id else None
        if not device or not device.com_port:
            return
        window = SerialMonitorWindow(self, device)
        self._monitors.append(window)
        window.bind(
            "<Destroy>",
            lambda event: self._monitors.remove(window)
            if event.widget is window and window in self._monitors
            else None,
        )

    def _who_holds_selected(self) -> None:
        device = self._current()
        if not device or not device.com_port:
            return
        if not self.admin:
            self._offer_elevation(
                "Windows разрешает перечисление хендлов только привилегированным "
                "программам, поэтому «кто занял порт» работает после повышения прав."
            )
            return
        port = device.com_port
        self._log(f"Ищу держателей {port}…", "info")

        def work() -> None:
            self._queue.put(("holders", find_port_holders(port, timeout=8.0), port))

        threading.Thread(target=work, daemon=True).start()

    def _scan_ports(self) -> None:
        ports = sorted({device.com_port for device in self.devices if device.com_port})
        if not ports:
            messagebox.showinfo("Порты", "В системе нет COM-портов.")
            return
        if not self.admin:
            self._offer_elevation(
                "Проверка занятости портов требует прав администратора: без них "
                "Windows не отдаёт список хендлов процессов."
            )
            return
        self._log(f"Проверяю занятость портов: {', '.join(ports)}…", "info")

        def work() -> None:
            result: dict[str, HolderReport] = {}
            for port in ports:
                result[port] = find_port_holders(port, timeout=6.0)
            self._queue.put(("busy", result))

        threading.Thread(target=work, daemon=True).start()

    def _copy_selected_id(self) -> None:
        device = self._current()
        if not device:
            return
        self.clipboard_clear()
        self.clipboard_append(device.instance_id)
        self._log("Instance ID скопирован в буфер", "info")

    def _open_devmgmt(self) -> None:
        try:
            setupapi.open_device_manager()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Диспетчер устройств", str(exc))

    def _export_report(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Сохранить отчёт PortGuard",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV для Excel", "*.csv")],
        )
        if not path:
            return
        try:
            save_report(path, self.devices)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Отчёт", f"Не удалось сохранить: {exc}")
            return
        self._log(f"Отчёт сохранён: {path}", "info")

    def _copy_summary(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(summary_text(self.devices))

    # ------------------------------------------------------------------
    # Права и журнал
    # ------------------------------------------------------------------
    def _elevate(self) -> None:
        ok, message = relaunch_as_admin()
        self._log(message, "info" if ok else "warn")
        if ok:
            self._on_close()
            self.destroy()

    def _offer_elevation(self, reason: str) -> None:
        if messagebox.askyesno(
            "Нужны права администратора",
            f"{reason}\n\nПерезапустить PortGuard от имени администратора?",
        ):
            self._elevate()

    def _log(self, text: str, tag: str = "info") -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{time.strftime('%H:%M:%S')}  ", "time")
        self.log_text.insert("end", f"{text}\n", tag)
        lines = int(self.log_text.index("end-1c").split(".")[0])
        if lines > 400:
            self.log_text.delete("1.0", f"{lines - 400}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _toggle_log(self) -> None:
        self._log_visible = not self._log_visible
        if self._log_visible:
            self._log_frame.grid()
            self.log_button.configure(text="Скрыть журнал")
        else:
            self._log_frame.grid_remove()
            self.log_button.configure(text="Показать журнал")

    # ------------------------------------------------------------------
    # Hot-plug и очередь событий
    # ------------------------------------------------------------------
    def _start_watcher(self) -> None:
        self._watcher = DeviceWatcher(lambda: self._queue.put(("refresh",)))
        if self._watcher.start():
            self._log("Hot-plug включён: подключения отслеживаются мгновенно", "info")
        else:
            self._watcher = None
            self._log(
                "Hot-plug недоступен — включён опрос каждые 5 секунд", "warn"
            )
            self._schedule_poll()

    def _schedule_poll(self) -> None:
        if self._poll_job:
            self.after_cancel(self._poll_job)
        self._poll_job = self.after(REFRESH_INTERVAL, self._poll_tick)

    def _poll_tick(self) -> None:
        self._poll_job = None
        if self._watcher:
            return
        self.refresh_async(quiet=True)
        self._schedule_poll()

    def _drain_queue(self) -> None:
        try:
            while True:
                message = self._queue.get_nowait()
                self._handle_message(message)
        except queue.Empty:
            pass
        self.after(80, self._drain_queue)

    def _handle_message(self, message: tuple) -> None:
        kind = message[0]
        if kind == "devices":
            _, devices, quiet = message
            self._apply_devices(devices, quiet)
        elif kind == "refresh":
            self.refresh_async(quiet=True)
        elif kind == "action":
            result = message[1]
            self._log(
                result.message + (f" — {result.detail}" if result.detail else ""),
                "info" if result.ok else "remove",
            )
            if not result.ok and result.detail:
                messagebox.showerror("Не удалось", f"{result.message}\n\n{result.detail}")
            self.after(300, self.refresh_async)
        elif kind == "holders":
            _, report, port = message
            self.busy_reports[port] = report
            device = self._current()
            if device and device.com_port == port:
                self.details.update_busy(report)
            self._log(
                f"{port}: " + ("занят — " + ", ".join(h.name for h in report.holders)
                               if report.holders else "свободен")
                if not report.error
                else f"{port}: {report.error}",
                "warn" if report.error or report.holders else "info",
            )
            self._show_holders_dialog(report)
        elif kind == "busy":
            self.busy_reports.update(message[1])
            busy_ports = [port for port, report in message[1].items() if report.holders]
            if busy_ports:
                for port in busy_ports:
                    holders = ", ".join(h.name for h in self.busy_reports[port].holders)
                    self._log(f"{port} занят: {holders}", "warn")
            else:
                self._log("Все COM-порты свободны", "info")
            device = self._current()
            if device and device.com_port:
                self.details.update_busy(self.busy_reports.get(device.com_port))
        elif kind == "error":
            self._refresh_pending = False
            self.refresh_button.configure(text="Обновить", state="normal")
            self._log(message[1], "remove")
        elif kind == "elevate":
            ok, text = message[1]
            self._log(text, "info" if ok else "warn")

    def _show_holders_dialog(self, report: HolderReport) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Кто занял {report.port}")
        dialog.geometry("620x420")
        dialog.configure(fg_color=theme.BG)
        dialog.transient(self)

        ctk.CTkLabel(
            dialog,
            text=f"{report.port}",
            font=theme.font(20, "bold"),
            text_color=theme.TEXT,
        ).pack(anchor="w", padx=20, pady=(18, 2))
        ctk.CTkLabel(
            dialog,
            text=report.device_path or "",
            font=theme.mono(9),
            text_color=theme.TEXT_MUTED,
        ).pack(anchor="w", padx=20)

        status_color = theme.ERROR if report.busy else theme.OK
        if report.error:
            status_text = (
                "Не проверено: нужны права администратора"
                if report.needs_admin
                else "Ошибка проверки"
            )
            status_color = theme.WARN
        elif report.busy:
            status_text = f"Занят: {len(report.holders)} процесс(ов)"
            status_color = theme.ERROR
        else:
            status_text = "Свободен"
            status_color = theme.OK
        ctk.CTkLabel(
            dialog,
            text=status_text,
            font=theme.font(12, "bold"),
            text_color=status_color,
        ).pack(anchor="w", padx=20, pady=(12, 4))

        body = ctk.CTkTextbox(
            dialog,
            font=theme.mono(10),
            fg_color=theme.PANEL,
            text_color=theme.TEXT_DIM,
            wrap="word",
            height=220,
        )
        body.pack(fill="both", expand=True, padx=20, pady=8)
        body.insert("1.0", report.describe())
        body.configure(state="disabled")

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=20, pady=(0, 16))

        if report.needs_admin and not self.admin:
            ctk.CTkButton(
                buttons,
                text="Перезапустить от администратора",
                fg_color=theme.ACCENT,
                hover_color=theme.ACCENT_HOVER,
                command=lambda: (dialog.destroy(), self._elevate()),
            ).pack(side="left")

        ctk.CTkButton(
            buttons,
            text="Закрыть",
            fg_color=theme.PANEL_ALT,
            hover_color=theme.BORDER,
            text_color=theme.TEXT,
            command=dialog.destroy,
        ).pack(side="right")

    # ------------------------------------------------------------------
    def _on_close(self) -> None:
        if self._poll_job:
            self.after_cancel(self._poll_job)
            self._poll_job = None
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        for window in list(self._monitors):
            try:
                window.destroy()
            except Exception:
                pass
        self._monitors.clear()


def run_gui() -> int:
    _enable_dpi_awareness()
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "hardkor88.portguard.2"
        )
    except Exception:
        pass
    ctk.set_appearance_mode("dark")
    app = PortGuardApp()
    app.mainloop()
    return 0
