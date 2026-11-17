"""Тесты экспорта отчёта."""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import unittest

from portguard.core.model import Device
from portguard.core.report import save_report, summary_text, to_csv, to_json


def _devices() -> list[Device]:
    return [
        Device(
            instance_id="USB\\VID_1A86&PID_7523\\ABC",
            name="USB-SERIAL CH340 (COM7)",
            com_port="COM7",
            vid=0x1A86,
            pid=0x7523,
            started=True,
            device_class="Ports",
            category="ports",
        ),
        Device(
            instance_id="ACPI\\PNP0C02\\0",
            name="Ресурсы системной платы",
            started=False,
            device_class="System",
            category="other",
        ),
    ]


class TestReport(unittest.TestCase):
    def test_json_contains_counts(self):
        payload = json.loads(to_json(_devices()))
        self.assertEqual(payload["counts"]["all"], 2)
        self.assertEqual(payload["devices"][0]["com_port"], "COM7")
        self.assertEqual(payload["devices"][0]["chip"], "CH340 / CH341 (USB-UART)")

    def test_csv_has_header_and_rows(self):
        text = to_csv(_devices())
        rows = list(csv.reader(io.StringIO(text), delimiter=";"))
        self.assertEqual(len(rows), 3)
        self.assertIn("Instance ID", rows[0])
        self.assertTrue(any("COM7" in "".join(row) for row in rows[1:]))

    def test_summary_text_mentions_port(self):
        text = summary_text(_devices())
        self.assertIn("COM7", text)
        self.assertIn("Устройств: 2", text)

    def test_save_json_and_csv(self):
        devices = _devices()
        for suffix in (".json", ".csv"):
            fd, path = tempfile.mkstemp(
                prefix="portguard_test_", suffix=suffix, dir="."
            )
            os.close(fd)
            try:
                save_report(path, devices)
                self.assertTrue(os.path.exists(path))
                encoding = "utf-8-sig" if suffix == ".csv" else "utf-8"
                with open(path, encoding=encoding) as handle:
                    content = handle.read()
                self.assertIn("COM7", content)
            finally:
                os.remove(path)


if __name__ == "__main__":
    unittest.main()
