"""Единая палитра и шрифты PortGuard."""

from __future__ import annotations

import customtkinter as ctk

# Фон и панели
BG = "#0f1216"
BG_ALT = "#141920"
PANEL = "#171d25"
PANEL_ALT = "#1d242e"
BORDER = "#252e3a"

# Текст
TEXT = "#e7eef7"
TEXT_DIM = "#93a1b3"
TEXT_MUTED = "#63707f"

# Акценты
ACCENT = "#4c9aff"
ACCENT_HOVER = "#3b7fd4"
ACCENT_SOFT = "#1b2b40"

# Состояния
OK = "#3fb950"
WARN = "#d29922"
ERROR = "#f85149"
DISABLED = "#6e7681"

STATUS_COLORS = {
    "ok": OK,
    "disabled": DISABLED,
    "error": ERROR,
    "absent": TEXT_MUTED,
    "stopped": WARN,
}

FONT_FAMILY = "Segoe UI"
MONO_FAMILY = "Cascadia Mono"


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)


def mono(size: int = 12, weight: str = "normal") -> ctk.CTkFont:
    return ctk.CTkFont(family=MONO_FAMILY, size=size, weight=weight)
