"""Экспорт отчёта о состоянии устройств (JSON/CSV) и сводка для буфера."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from .model import Device, summary

CSV_FIELDS = (
    ("instance_id", "Instance ID"),
    ("name", "Устройство"),
    ("device_class", "Класс"),
    ("com_port", "COM"),
    ("vid_pid", "VID:PID"),
    ("chip", "Чип/плата"),
    ("status", "Состояние"),
    ("manufacturer", "Производитель"),
    ("driver_version", "Версия драйвера"),
    ("location", "Расположение"),
    ("parent_id", "Родитель"),
)


def build_payload(devices: list[Device]) -> dict:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": summary(devices),
        "devices": [device.to_dict() for device in devices],
    }


def to_json(devices: list[Device]) -> str:
    return json.dumps(build_payload(devices), ensure_ascii=False, indent=2)


def to_csv(devices: list[Device]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow([title for _, title in CSV_FIELDS])
    for device in devices:
        data = device.to_dict()
        writer.writerow([data.get(key, "") for key, _ in CSV_FIELDS])
    return buffer.getvalue()


def save_report(path: str, devices: list[Device]) -> None:
    """Сохраняет отчёт, выбирая формат по расширению."""
    if path.lower().endswith(".json"):
        text = to_json(devices)
        encoding = "utf-8"
    else:
        text = to_csv(devices)
        encoding = "utf-8-sig"  # чтобы Excel не ломал кириллицу
    with open(path, "w", encoding=encoding, newline="") as handle:
        handle.write(text)


def summary_text(devices: list[Device]) -> str:
    """Короткая сводка для статус-бара и буфера обмена."""
    counts = summary(devices)
    ports = [d for d in devices if d.com_port]
    problem = [d for d in devices if d.has_problem]
    lines = [
        f"PortGuard · {datetime.now():%d.%m.%Y %H:%M:%S}",
        f"Устройств: {counts['all']} · COM-портов: {len(ports)} · "
        f"с проблемами: {len(problem)}",
    ]
    if ports:
        lines.append("")
        lines.append("COM-порты:")
        for device in sorted(ports, key=lambda d: d.com_port or ""):
            chip = device.chip_name or device.vendor_name or device.manufacturer
            suffix = f" — {chip}" if chip else ""
            lines.append(f"  {device.com_port}: {device.display_name}{suffix}")
    if problem:
        lines.append("")
        lines.append("Проблемные устройства:")
        for device in problem:
            lines.append(f"  {device.display_name}: {device.status_text}")
    return "\n".join(lines)
