"""Тесты модели: разбор VID/PID, статусы, категории, сводка."""

from __future__ import annotations

import unittest

from portguard.core.model import (
    Device,
    category_of,
    parse_serial,
    parse_vid_pid,
    sort_key,
    summary,
)


class TestVidPid(unittest.TestCase):
    def test_full_id(self):
        self.assertEqual(
            parse_vid_pid(["USB\\VID_1A86&PID_7523&REV_0264"]), (0x1A86, 0x7523)
        )

    def test_lowercase(self):
        self.assertEqual(
            parse_vid_pid(["usb\\vid_10c4&pid_ea60"]), (0x10C4, 0xEA60)
        )

    def test_vid_only(self):
        self.assertEqual(parse_vid_pid(["HID\\VID_046D"]), (0x046D, None))

    def test_empty(self):
        self.assertEqual(parse_vid_pid([]), (None, None))
        self.assertEqual(parse_vid_pid(["PCI\\VEN_10EC&DEV_8168"]), (None, None))


class TestSerial(unittest.TestCase):
    def test_plain_serial(self):
        self.assertEqual(
            parse_serial("USB\\VID_1A86&PID_7523\\ABC123"), "ABC123"
        )

    def test_generated_instance(self):
        self.assertIsNone(parse_serial("USB\\VID_1A86&PID_7523\\5&2A3B4C&0&1"))

    def test_too_short(self):
        self.assertIsNone(parse_serial("USB\\A"))


class TestStatus(unittest.TestCase):
    def test_ok(self):
        device = Device(instance_id="X\\1", started=True)
        self.assertEqual(device.status_kind, "ok")
        self.assertEqual(device.short_status, "Работает")
        self.assertFalse(device.has_problem)

    def test_disabled(self):
        device = Device(instance_id="X\\1", problem=22, disableable=True)
        self.assertEqual(device.status_kind, "disabled")
        self.assertEqual(device.short_status, "Отключено")
        self.assertTrue(device.has_problem)

    def test_failed_start_has_code_in_text(self):
        device = Device(instance_id="X\\1", problem=10)
        self.assertEqual(device.status_kind, "error")
        self.assertIn("10", device.status_text)
        self.assertTrue(device.has_problem)

    def test_stopped_is_not_a_problem(self):
        # Пассивные ACPI-устройства не запущены, но это норма.
        device = Device(instance_id="ACPI\\PNP0C02\\0", started=False)
        self.assertEqual(device.status_kind, "stopped")
        self.assertFalse(device.has_problem)

    def test_unknown_problem_code(self):
        device = Device(instance_id="X\\1", problem=999)
        self.assertIn("999", device.short_status)


class TestChip(unittest.TestCase):
    def test_known_pair(self):
        device = Device(instance_id="USB\\X", vid=0x1A86, pid=0x7523)
        self.assertIn("CH340", device.chip_name)

    def test_esp_native_usb(self):
        device = Device(instance_id="USB\\X", vid=0x303A, pid=0x1001)
        self.assertIn("ESP32", device.chip_name)

    def test_description_hint(self):
        device = Device(instance_id="USB\\X", description="USB-SERIAL CH340 (COM3)")
        self.assertIn("CH340", device.chip_name)

    def test_vendor_fallback(self):
        device = Device(instance_id="USB\\X", vid=0x2341, pid=0x9999)
        self.assertEqual(device.chip_name, "")
        self.assertEqual(device.vendor_name, "Arduino")


class TestCategory(unittest.TestCase):
    def test_port_wins(self):
        device = Device(instance_id="USB\\X", com_port="COM7", device_class="Ports")
        self.assertEqual(category_of(device), "ports")

    def test_class_mapping(self):
        device = Device(instance_id="HID\\X", device_class="HIDClass")
        self.assertEqual(category_of(device), "hid")

    def test_bluetooth_by_instance(self):
        device = Device(instance_id="BTHENUM\\{0000}\\7&1")
        self.assertEqual(category_of(device), "bluetooth")

    def test_usb_by_instance(self):
        device = Device(instance_id="USB\\VID_1234&PID_5678\\1", vid=0x1234)
        self.assertEqual(category_of(device), "usb")


class TestSummaryAndSort(unittest.TestCase):
    def test_counts(self):
        devices = [
            Device(instance_id="A", com_port="COM1", started=True, category="ports"),
            Device(instance_id="B", problem=22, category="usb"),
            Device(instance_id="C", started=True, category="usb"),
        ]
        counts = summary(devices)
        self.assertEqual(counts["all"], 3)
        self.assertEqual(counts["ports"], 1)
        self.assertEqual(counts["usb"], 2)
        self.assertEqual(counts["problem"], 1)

    def test_problem_first(self):
        ok = Device(instance_id="A", started=True, name="AAA")
        broken = Device(instance_id="B", problem=10, name="ZZZ")
        ordered = sorted([ok, broken], key=sort_key)
        self.assertIs(ordered[0], broken)


if __name__ == "__main__":
    unittest.main()
