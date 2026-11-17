"""Командная строка PortGuard.

GUI запускается без аргументов. Все остальные команды нужны для диагностики,
скриптов и проверки на машине без рабочего стола:

    python -m portguard                      # графическое приложение
    python -m portguard list                 # таблица всех устройств
    python -m portguard list --problems      # только проблемные
    python -m portguard ports                # только COM-порты
    python -m portguard holders COM3         # кто занял порт
    python -m portguard action disable <id>  # отключить устройство
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys

from . import __version__
from .core.model import CATEGORY_TITLES, Device, sort_key, summary
from .core.setupapi import enumerate_devices


def _prepare_stdio() -> None:
    """
    UTF-8 для CLI независимо от локали и кодовой страницы консоли.

    Иначе на машинах с CP866/CP1251 русские названия устройств превращаются
    в «кракозябры», а при перенаправлении в файл — в знаки вопроса.
    """
    try:
        if ctypes.windll.kernel32.GetConsoleWindow():
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _ensure_console() -> None:
    """
    В оконной сборке PyInstaller у процесса нет sys.stdout.

    Если PortGuard.exe запустили из терминала с аргументами (list, holders…),
    возвращаем вывод: сначала пробуем унаследованный stdout (работает и при
    перенаправлении в файл), затем подключаемся к консоли родителя.
    """
    if sys.stdout is not None:
        return

    try:
        import msvcrt
        import os

        handle = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        invalid = ctypes.c_void_p(-1).value
        if handle and handle != invalid:
            descriptor = msvcrt.open_osfhandle(handle, os.O_WRONLY)
            stream = open(
                descriptor, "w", encoding="utf-8", buffering=1, closefd=False
            )
            sys.stdout = stream
            sys.stderr = stream
            return
    except Exception:
        pass

    try:
        ctypes.windll.kernel32.AttachConsole(-1)
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys.stderr = sys.stdout
    except Exception:
        pass


def _cut(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text.ljust(width)
    return text[: width - 1] + "…"


def _select(
    devices: list[Device],
    category: str | None = None,
    problems: bool = False,
    search: str | None = None,
) -> list[Device]:
    result = devices
    if category and category != "all":
        if category == "problem":
            result = [d for d in result if d.has_problem]
        else:
            result = [d for d in result if d.category == category]
    if problems:
        result = [d for d in result if d.has_problem]
    if search:
        needle = search.casefold()
        result = [
            d
            for d in result
            if needle in d.display_name.casefold()
            or needle in d.instance_id.casefold()
            or needle in (d.com_port or "").casefold()
            or needle in d.vid_pid_text.casefold()
            or needle in d.chip_name.casefold()
            or needle in d.manufacturer.casefold()
        ]
    return result


def _print_table(devices: list[Device]) -> None:
    header = (
        f"{'ПОРТ':<6} {'УСТРОЙСТВО':<42} {'КЛАСС':<24} "
        f"{'VID:PID':<10} {'СТАТУС':<34} ID"
    )
    print(header)
    print("-" * len(header))
    for device in devices:
        print(
            f"{_cut(device.com_port or '-', 6)} "
            f"{_cut(device.display_name, 42)} "
            f"{_cut(device.device_class, 24)} "
            f"{_cut(device.vid_pid_text or '-', 10)} "
            f"{_cut(device.status_text, 34)} "
            f"{device.instance_id}"
        )


def cmd_list(args: argparse.Namespace) -> int:
    devices = enumerate_devices()
    selected = _select(devices, args.category, args.problems, args.search)
    selected.sort(key=sort_key)
    if args.json:
        payload = {
            "version": __version__,
            "total": len(devices),
            "shown": len(selected),
            "counts": summary(devices),
            "devices": [d.to_dict() for d in selected],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    _print_table(selected)
    counts = summary(devices)
    print(
        f"\nВсего устройств: {counts['all']} · "
        f"портов: {counts.get('ports', 0)} · "
        f"с проблемами: {counts['problem']}"
    )
    return 0


def cmd_ports(args: argparse.Namespace) -> int:
    devices = [d for d in enumerate_devices() if d.com_port]
    devices.sort(key=lambda d: d.com_port or "")
    if args.json:
        print(json.dumps([d.to_dict() for d in devices], ensure_ascii=False, indent=2))
        return 0
    if not devices:
        print("COM-портов не найдено.")
        return 0
    for device in devices:
        chip = device.chip_name or device.vendor_name or device.manufacturer
        print(f"{device.com_port}  {device.display_name}")
        print(f"        {chip or '—'}")
        print(f"        {device.vid_pid_text}  ·  {device.status_text}")
    return 0


def cmd_holders(args: argparse.Namespace) -> int:
    from .core.holders import find_port_holders

    report = find_port_holders(args.port)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0
    print(report.describe())
    return 0 if report.holders else 2


def cmd_action(args: argparse.Namespace) -> int:
    from .core.setupapi import (
        eject_device,
        restart_device,
        set_device_enabled,
    )

    if args.what == "enable":
        result = set_device_enabled(args.instance_id, True)
    elif args.what == "disable":
        result = set_device_enabled(args.instance_id, False)
    elif args.what == "restart":
        result = restart_device(args.instance_id)
    else:
        result = eject_device(args.instance_id)
    print(("OK  " if result.ok else "ОШИБКА  ") + result.message)
    if result.detail:
        print(result.detail)
    return 0 if result.ok else 1


def cmd_monitor(args: argparse.Namespace) -> int:
    """Терминал в консоли — на случай, если GUI недоступен."""
    import time

    from .core.serial_monitor import SerialSession

    session = SerialSession(args.port, baudrate=args.baud)
    session.open()
    print(f"{args.port} @ {args.baud}. Выход — Ctrl+C.")
    try:
        while True:
            data = session.read_nowait()
            if data:
                sys.stdout.write(data.decode("utf-8", "replace"))
                sys.stdout.flush()
            time.sleep(0.02)
    except KeyboardInterrupt:
        print("\nЗакрываю порт.")
    finally:
        session.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="portguard",
        description="PortGuard — менеджер подключённых устройств Windows",
    )
    parser.add_argument("--version", action="version", version=f"PortGuard {__version__}")
    sub = parser.add_subparsers(dest="command")

    p_list = sub.add_parser("list", help="таблица устройств")
    p_list.add_argument("--json", action="store_true", help="вывод в JSON")
    p_list.add_argument("--problems", action="store_true", help="только проблемные")
    p_list.add_argument("--category", choices=list(CATEGORY_TITLES), help="фильтр по категории")
    p_list.add_argument("--search", help="поиск по имени, ID, VID:PID")
    p_list.set_defaults(func=cmd_list)

    p_ports = sub.add_parser("ports", help="только COM-порты")
    p_ports.add_argument("--json", action="store_true")
    p_ports.set_defaults(func=cmd_ports)

    p_hold = sub.add_parser("holders", help="кто занимает COM-порт")
    p_hold.add_argument("port", help="имя порта, например COM3")
    p_hold.add_argument("--json", action="store_true")
    p_hold.set_defaults(func=cmd_holders)

    p_action = sub.add_parser("action", help="управление устройством")
    p_action.add_argument("what", choices=["enable", "disable", "restart", "eject"])
    p_action.add_argument("instance_id", help="instance id, например USB\\VID_1A86&PID_7523\\5&2A3B")
    p_action.set_defaults(func=cmd_action)

    p_mon = sub.add_parser("monitor", help="терминал COM-порта в консоли")
    p_mon.add_argument("port")
    p_mon.add_argument("--baud", type=int, default=115200)
    p_mon.set_defaults(func=cmd_monitor)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        _ensure_console()
        _prepare_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        from .ui.app import run_gui

        return run_gui()
    try:
        return args.func(args)
    except OSError as exc:
        print(f"Ошибка Windows: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
