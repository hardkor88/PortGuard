"""Права администратора: проверка и перезапуск с повышением."""

from __future__ import annotations

import os
import subprocess
import sys

from . import winapi as w

ERROR_CANCELLED = 1223


def is_admin() -> bool:
    """Запущено ли приложение с повышенными правами."""
    try:
        return bool(w.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _command() -> tuple[str, str]:
    """Возвращает (exe, аргументы) для повторного запуска себя же."""
    if getattr(sys, "frozen", False):
        exe = sys.executable
        args = sys.argv[1:]
    else:
        exe = sys.executable
        args = ["-m", "portguard", *sys.argv[1:]]
    return exe, subprocess.list2cmdline(args)


def relaunch_as_admin() -> tuple[bool, str]:
    """
    Перезапускает PortGuard через UAC.

    Возвращает (запущено, сообщение). Пользователь может отменить запрос —
    тогда вернётся False с кодом 1223.
    """
    exe, params = _command()
    try:
        result = w.shell32.ShellExecuteW(None, "runas", exe, params, os.getcwd(), 1)
    except Exception as exc:  # pragma: no cover - зависит от оболочки
        return False, str(exc)
    code = int(result or 0)
    if code > 32:
        return True, "Запрошен перезапуск с правами администратора"
    if code == ERROR_CANCELLED:
        return False, "Запрос прав администратора отменён"
    return False, f"Не удалось перезапустить (код {code})"
