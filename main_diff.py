--- main.py (原始)


+++ main.py (修改后)
"""
PortGuard - COM Port Monitor for Electronics Developers
Monitor and manage COM ports in real-time for Arduino, ESP8266, ESP32 development.
"""

import customtkinter as ctk
from tkinter import messagebox, ClipboardError
import serial.tools.list_ports
import psutil
import threading
import time
import sys
import os

# Configure customtkinter appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class PortInfo:
    """Represents information about a COM port."""

    def __init__(self, port_name, description, status="Свободен", pid=None, process_name=None):
        self.port_name = port_name
        self.description = description
        self.status = status
        self.pid = pid
        self.process_name = process_name

    def is_busy(self):
        return self.status == "Занят"


class PortMonitor:
    """Background thread for monitoring COM ports."""

    def __init__(self, callback, interval=1.5):
        self.callback = callback
        self.interval = interval
        self.running = False
        self.thread = None
        self.last_ports = set()

    def start(self):
        """Start the monitoring thread."""
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the monitoring thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)

    def _check_port_status(self, port_name):
        """Check if a port is busy and get process info if possible."""
        try:
            # Try to open the port to check if it's available
            test_serial = serial.Serial(port_name)
            test_serial.close()
            return "Свободен", None, None
        except serial.SerialException:
            # Port is busy, try to find which process is using it
            pid, process_name = self._find_process_using_port(port_name)
            if pid:
                return "Занят", pid, process_name
            else:
                return "Занят", None, None
        except PermissionError:
            pid, process_name = self._find_process_using_port(port_name)
            if pid:
                return "Занят", pid, process_name
            else:
                return "Занят", None, None
        except Exception:
            return "Занят", None, None

    def _find_process_using_port(self, port_name):
        """Try to find which process is using the port."""
        try:
            # Get all processes and check their open files/connections
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    # Check if process has any connections or files related to the port
                    # This is a heuristic approach since Windows doesn't expose this directly
                    pinfo = proc.info
                    pid = pinfo['pid']
                    name = pinfo['name']

                    # Try to match common IDE/editor names that might hold ports
                    if name and any(ide in name.lower() for ide in
                                   ['arduino', 'thonny', 'pycharm', 'vscode', 'python',
                                    'platformio', 'esp-idf', 'moba', 'putty', 'terminal']):
                        # We can't definitively prove it's this process without driver-level access
                        # So we return what we found with lower confidence
                        pass

                    # On Windows, we can't easily determine which process has a COM port open
                    # without special drivers or WMI queries
                    # Return generic info
                    continue

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            # Try WMI approach for better detection
            try:
                import wmi
                w = wmi.WMI()
                for ser in w.Win32_SerialPort():
                    if ser.DeviceID == port_name:
                        # Try to get associated PnP entity
                        pass
            except (ImportError, Exception):
                pass

            return None, None

        except Exception:
            return None, None

    def _get_port_description(self, port_info):
        """Extract chip description from port info."""
        desc = port_info.description or "Unknown Device"

        # Common chip identifiers
        chip_names = {
            'CH340': ['CH340', 'CH341'],
            'CP2102': ['CP2102', 'CP2104', 'CP2109', 'Silicon Labs'],
            'FTDI': ['FTDI', 'FT232', 'FT2232', 'FT4232'],
            'NodeMCU': ['NodeMCU', 'ESP8266'],
            'ESP32': ['ESP32', 'ESP-32'],
            'Arduino': ['Arduino', 'ATmega'],
            'Prolific': ['Prolific', 'PL2303'],
            'FT230X': ['FT230X', 'FT231X']
        }

        for chip, keywords in chip_names.items():
            for keyword in keywords:
                if keyword.lower() in desc.lower():
                    return chip

        return desc

    def _monitor_loop(self):
        """Main monitoring loop."""
        while self.running:
            try:
                ports = serial.tools.list_ports.comports()
                current_ports = set()
                port_list = []

                for port in ports:
                    port_name = port.device
                    current_ports.add(port_name)

                    description = self._get_port_description(port)
                    status, pid, process_name = self._check_port_status(port_name)

                    port_info = PortInfo(
                        port_name=port_name,
                        description=description,
                        status=status,
                        pid=pid,
                        process_name=process_name
                    )
                    port_list.append(port_info)

                # Check for changes
                if current_ports != self.last_ports or self.callback is not None:
                    self.last_ports = current_ports
                    if self.callback:
                        self.callback(port_list)

                time.sleep(self.interval)

            except Exception as e:
                print(f"Monitoring error: {e}")
                time.sleep(self.interval)


class PortCard(ctk.CTkFrame):
    """A card widget displaying information about a single COM port."""

    def __init__(self, parent, port_info, on_free_port, on_copy_name):
        super().__init__(parent, corner_radius=10, fg_color="#2b2b2b")

        self.port_info = port_info
        self.on_free_port = on_free_port
        self.on_copy_name = on_copy_name

        self._create_widgets()

    def _create_widgets(self):
        """Create the card widgets."""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=0)

        # Port name and description (left side)
        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=0, sticky="w", padx=15, pady=10)
        info_frame.grid_columnconfigure(0, weight=1)

        # Port name
        self.name_label = ctk.CTkLabel(
            info_frame,
            text=self.port_info.port_name,
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w"
        )
        self.name_label.grid(row=0, column=0, sticky="w")

        # Description
        self.desc_label = ctk.CTkLabel(
            info_frame,
            text=self.port_info.description,
            font=ctk.CTkFont(size=12),
            text_color="#aaaaaa",
            anchor="w"
        )
        self.desc_label.grid(row=1, column=0, sticky="w")

        # Status badge (center)
        status_color = "#27ae60" if self.port_info.status == "Свободен" else "#e74c3c"
        self.status_badge = ctk.CTkLabel(
            self,
            text=self.port_info.status,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="white",
            fg_color=status_color,
            corner_radius=5,
            padx=15,
            pady=5
        )
        self.status_badge.grid(row=0, column=1, padx=10, pady=10)

        # Action buttons (right side)
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, sticky="e", padx=15, pady=10)

        # Copy button
        self.copy_btn = ctk.CTkButton(
            btn_frame,
            text="Копировать",
            width=90,
            height=30,
            font=ctk.CTkFont(size=12),
            command=self._copy_name
        )
        self.copy_btn.pack(side="left", padx=5)

        # Free port button (only if busy)
        if self.port_info.is_busy():
            self.free_btn = ctk.CTkButton(
                btn_frame,
                text="Освободить",
                width=90,
                height=30,
                font=ctk.CTkFont(size=12),
                fg_color="#e74c3c",
                hover_color="#c0392b",
                command=self._free_port
            )
            self.free_btn.pack(side="left", padx=5)

            # Show process info if available
            if self.port_info.process_name:
                process_label = ctk.CTkLabel(
                    self,
                    text=f"Процесс: {self.port_info.process_name} (PID: {self.port_info.pid})",
                    font=ctk.CTkFont(size=10),
                    text_color="#e74c3c",
                    anchor="w"
                )
                process_label.grid(row=1, column=2, sticky="e", padx=15)

    def _copy_name(self):
        """Copy port name to clipboard."""
        try:
            self.on_copy_name(self.port_info.port_name)
        except Exception:
            pass

    def _free_port(self):
        """Attempt to free the port by terminating the holding process."""
        if self.port_info.pid:
            confirm = messagebox.askyesno(
                "Подтверждение",
                f"Завершить процесс {self.port_info.process_name} (PID: {self.port_info.pid})?\n\n"
                f"Это освободит порт {self.port_info.port_name}, но может привести к потере данных."
            )
            if confirm:
                self.on_free_port(self.port_info.pid, self.port_info.process_name)
        else:
            messagebox.showinfo(
                "Информация",
                f"Не удалось определить процесс, удерживающий порт {self.port_info.port_name}.\n\n"
                f"Попробуйте закрыть программы вручную:\n"
                f"- Arduino IDE\n- Thonny\n- Терминалы (Putty, MobaXterm)\n- Python скрипты"
            )


class PortGuardApp(ctk.CTk):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.title("PortGuard - Монитор COM портов")
        self.geometry("900x600")
        self.minsize(700, 400)

        self.monitor = None
        self.port_cards = []

        self._setup_ui()
        self._start_monitoring()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_ui(self):
        """Setup the user interface."""
        # Main container
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        # Header
        header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        header_frame.grid_columnconfigure(0, weight=1)

        # Title
        title_label = ctk.CTkLabel(
            header_frame,
            text="🔌 PortGuard",
            font=ctk.CTkFont(size=28, weight="bold"),
            anchor="w"
        )
        title_label.grid(row=0, column=0, sticky="w")

        # Subtitle
        subtitle_label = ctk.CTkLabel(
            header_frame,
            text="Мониторинг COM портов для разработчиков электроники",
            font=ctk.CTkFont(size=14),
            text_color="#aaaaaa",
            anchor="w"
        )
        subtitle_label.grid(row=1, column=0, sticky="w")

        # Control buttons
        control_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        control_frame.grid(row=0, column=1, rowspan=2, sticky="e")

        # Refresh button
        self.refresh_btn = ctk.CTkButton(
            control_frame,
            text="🔄 Обновить список",
            width=140,
            height=35,
            font=ctk.CTkFont(size=13),
            command=self._manual_refresh
        )
        self.refresh_btn.pack(side="left", padx=5)

        # Auto-refresh toggle
        self.auto_refresh_var = ctk.BooleanVar(value=True)
        self.auto_refresh_switch = ctk.CTkSwitch(
            control_frame,
            text="Автообновление",
            variable=self.auto_refresh_var,
            font=ctk.CTkFont(size=12),
            command=self._toggle_auto_refresh
        )
        self.auto_refresh_switch.pack(side="left", padx=10)

        # Scrollable frame for port cards
        self.scroll_frame = ctk.CTkScrollableFrame(
            self.main_frame,
            corner_radius=10,
            fg_color="#1a1a1a"
        )
        self.scroll_frame.grid(row=1, column=0, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Status bar
        status_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        status_frame.grid(row=2, column=0, sticky="ew", pady=(20, 0))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="● Мониторинг активен",
            font=ctk.CTkFont(size=12),
            text_color="#27ae60",
            anchor="w"
        )
        self.status_label.pack(side="left")

        self.port_count_label = ctk.CTkLabel(
            status_frame,
            text="Портов найдено: 0",
            font=ctk.CTkFont(size=12),
            text_color="#aaaaaa",
            anchor="e"
        )
        self.port_count_label.pack(side="right")

    def _start_monitoring(self):
        """Start the port monitoring thread."""
        self.monitor = PortMonitor(callback=self._update_port_list, interval=1.5)
        self.monitor.start()

    def _stop_monitoring(self):
        """Stop the port monitoring thread."""
        if self.monitor:
            self.monitor.stop()
            self.monitor = None

    def _toggle_auto_refresh(self):
        """Toggle auto-refresh functionality."""
        if self.auto_refresh_var.get():
            if not self.monitor:
                self._start_monitoring()
            self.status_label.configure(text="● Мониторинг активен", text_color="#27ae60")
        else:
            self._stop_monitoring()
            self.status_label.configure(text="○ Мониторинг остановлен", text_color="#e74c3c")

    def _manual_refresh(self):
        """Manually trigger a port list refresh."""
        try:
            # Temporarily stop and restart monitoring to force immediate refresh
            was_running = self.monitor is not None
            if self.monitor:
                self.monitor.stop()

            # Force immediate update
            ports = serial.tools.list_ports.comports()
            port_list = []
            for port in ports:
                port_name = port.device
                description = self._get_port_description(port)
                status, pid, process_name = self._check_port_status(port_name)
                port_list.append(PortInfo(port_name, description, status, pid, process_name))

            self._update_port_list(port_list)

            # Restart if it was running
            if was_running and self.auto_refresh_var.get():
                self.monitor = PortMonitor(callback=self._update_port_list, interval=1.5)
                self.monitor.start()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить список портов:\n{str(e)}")

    def _get_port_description(self, port_info):
        """Extract chip description from port info."""
        desc = port_info.description or "Unknown Device"

        chip_names = {
            'CH340': ['CH340', 'CH341'],
            'CP2102': ['CP2102', 'CP2104', 'CP2109', 'Silicon Labs'],
            'FTDI': ['FTDI', 'FT232', 'FT2232', 'FT4232'],
            'NodeMCU': ['NodeMCU', 'ESP8266'],
            'ESP32': ['ESP32', 'ESP-32'],
            'Arduino': ['Arduino', 'ATmega'],
            'Prolific': ['Prolific', 'PL2303'],
            'FT230X': ['FT230X', 'FT231X']
        }

        for chip, keywords in chip_names.items():
            for keyword in keywords:
                if keyword.lower() in desc.lower():
                    return chip

        return desc

    def _check_port_status(self, port_name):
        """Check if a port is busy."""
        try:
            test_serial = serial.Serial(port_name)
            test_serial.close()
            return "Свободен", None, None
        except (serial.SerialException, PermissionError, OSError):
            return "Занят", None, None
        except Exception:
            return "Занят", None, None

    def _update_port_list(self, port_list):
        """Update the UI with the new port list (called from monitoring thread)."""
        # Schedule UI update on main thread
        self.after(0, lambda: self._refresh_port_cards(port_list))

    def _refresh_port_cards(self, port_list):
        """Refresh port cards in the UI."""
        try:
            # Clear existing cards
            for card in self.port_cards:
                card.destroy()
            self.port_cards.clear()

            # Create new cards
            if not port_list:
                no_ports_label = ctk.CTkLabel(
                    self.scroll_frame,
                    text="COM порты не обнаружены.\nПодключите устройство (Arduino, ESP8266, ESP32 и т.д.)",
                    font=ctk.CTkFont(size=14),
                    text_color="#aaaaaa",
                    justify="center"
                )
                no_ports_label.grid(row=0, column=0, pady=50)
            else:
                for idx, port_info in enumerate(port_list):
                    card = PortCard(
                        self.scroll_frame,
                        port_info,
                        on_free_port=self._free_port,
                        on_copy_name=self._copy_to_clipboard
                    )
                    card.grid(row=idx, column=0, sticky="ew", padx=10, pady=5)
                    self.port_cards.append(card)

            # Update port count
            self.port_count_label.configure(text=f"Портов найдено: {len(port_list)}")

        except Exception as e:
            print(f"UI update error: {e}")

    def _free_port(self, pid, process_name):
        """Attempt to free a port by terminating the process."""
        try:
            process = psutil.Process(pid)
            process_name_actual = process.name()

            confirm = messagebox.askyesno(
                "Финальное подтверждение",
                f"Вы уверены, что хотите завершить процесс?\n\n"
                f"Процесс: {process_name_actual}\n"
                f"PID: {pid}\n\n"
                f"⚠️ Это действие необратимо! Несохраненные данные будут потеряны."
            )

            if confirm:
                process.terminate()
                # Wait a bit for graceful termination
                time.sleep(0.5)

                if process.is_running():
                    # Force kill if still running
                    process.kill()

                messagebox.showinfo(
                    "Успех",
                    f"Процесс '{process_name_actual}' завершен.\n"
                    f"Порт должен быть освобожден."
                )

                # Trigger refresh
                self._manual_refresh()

        except psutil.NoSuchProcess:
            messagebox.showinfo("Информация", "Процесс уже завершен.")
        except psutil.AccessDenied:
            messagebox.showerror(
                "Ошибка доступа",
                "Не удалось завершить процесс.\n"
                "Запустите приложение от имени администратора."
            )
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось завершить процесс:\n{str(e)}")

    def _copy_to_clipboard(self, text):
        """Copy text to clipboard."""
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()  # Required for clipboard to work properly

            # Show temporary feedback
            original_text = self.status_label.cget("text")
            original_color = self.status_label.cget("text_color")
            self.status_label.configure(text=f"✓ Скопировано: {text}", text_color="#3498db")
            self.after(2000, lambda: self.status_label.configure(text=original_text, text_color=original_color))

        except ClipboardError:
            messagebox.showerror("Ошибка", "Не удалось скопировать в буфер обмена.")
        except Exception:
            pass

    def _on_closing(self):
        """Handle window close event."""
        self._stop_monitoring()
        self.destroy()


def main():
    """Main entry point."""
    try:
        app = PortGuardApp()
        app.mainloop()
    except Exception as e:
        # Last resort error handling
        error_msg = f"Критическая ошибка приложения:\n{str(e)}\n\n" \
                   f"Убедитесь, что все зависимости установлены:\n" \
                   f"pip install customtkinter pyserial psutil"

        if 'tkinter' in str(e).lower():
            error_msg += "\n\nТакже убедитесь, что tkinter установлен в вашей системе Python."

        print(error_msg, file=sys.stderr)

        # Try to show error dialog even if main app failed
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("PortGuard - Ошибка запуска", error_msg)
            root.destroy()
        except Exception:
            pass

        sys.exit(1)


if __name__ == "__main__":
    main()
