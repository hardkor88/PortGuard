"""Тесты работы с Windows: перечисление, пути устройств, разбор хендлов."""

from __future__ import annotations

import ctypes
import json
import sys
import unittest
from ctypes import POINTER, byref, cast

from portguard.core import holders, winapi
from portguard.core.setupapi import enumerate_devices, get_dos_device_path


class TestEnumeration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.devices = enumerate_devices()

    def test_not_empty(self):
        self.assertGreater(len(self.devices), 0)

    def test_instances_have_ids_and_names(self):
        for device in self.devices[:40]:
            self.assertTrue(device.instance_id)
            self.assertTrue(device.display_name)
            self.assertIn(
                device.status_kind,
                {"ok", "disabled", "error", "stopped", "absent"},
            )

    def test_ports_have_com_names(self):
        for device in self.devices:
            if device.com_port:
                self.assertRegex(device.com_port, r"^COM\d+$")

    def test_devices_are_json_serializable(self):
        payload = json.dumps([device.to_dict() for device in self.devices[:10]])
        self.assertIn("instance_id", payload)


class TestDosPath(unittest.TestCase):
    def test_com1_path(self):
        path = get_dos_device_path("COM1")
        if path is None:
            self.skipTest("COM1 отсутствует на этой машине")
        self.assertTrue(path.startswith("\\Device\\"))

    def test_missing_port(self):
        self.assertIsNone(get_dos_device_path("COM250"))


class TestHandleParsing(unittest.TestCase):
    def test_iter_handles(self):
        buffer = ctypes.create_string_buffer(4096)
        info = cast(buffer, POINTER(winapi.SYSTEM_HANDLE_INFORMATION_EX)).contents
        info.NumberOfHandles = 2
        array = cast(
            byref(info.Handles),
            POINTER(winapi.SYSTEM_HANDLE_TABLE_ENTRY_INFO_EX * 2),
        ).contents
        array[0].UniqueProcessId = 111
        array[0].HandleValue = 0x14
        array[1].UniqueProcessId = 222
        array[1].HandleValue = 0x28

        self.assertEqual(
            list(holders._iter_handles(buffer)),
            [(111, 0x14), (222, 0x28)],
        )

    def test_unicode_string_reader(self):
        text = "File"
        encoded = text.encode("utf-16-le")
        encoded_buffer = ctypes.create_string_buffer(encoded)
        string = winapi.UNICODE_STRING()
        string.Length = len(encoded)
        string.MaximumLength = len(encoded) + 2
        string.Buffer = ctypes.cast(encoded_buffer, ctypes.c_void_p).value

        buffer = ctypes.create_string_buffer(64)
        ctypes.memmove(buffer, ctypes.byref(string), ctypes.sizeof(string))
        self.assertEqual(holders._read_unicode_string(buffer), "File")
        self.assertEqual(encoded_buffer.raw[: len(encoded)], encoded)


class TestHolderReport(unittest.TestCase):
    def test_needs_admin_message(self):
        report = holders.HolderReport(
            port="COM9", error="нет доступа", needs_admin=True
        )
        text = report.describe()
        self.assertIn("администратор", text)
        self.assertIn("COM9", text)
        self.assertFalse(report.busy)

    def test_busy_flag(self):
        report = holders.HolderReport(
            port="COM3",
            holders=[holders.Holder(pid=1, name="test.exe", path="\\Device\\Serial1")],
        )
        self.assertTrue(report.busy)
        self.assertIn("test.exe", report.describe())

    def test_scan_returns_quickly(self):
        """Скан не должен подвешивать вызывающий поток дольше таймаута."""
        report = holders.find_port_holders("COM1", timeout=2.0)
        self.assertIsInstance(report, holders.HolderReport)
        self.assertLess(report.elapsed, 6.0)
        if report.needs_admin:
            self.assertIn("администратор", report.describe())


if __name__ == "__main__":
    unittest.main()
