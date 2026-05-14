import importlib.util
import sys
import tempfile
import unittest
import subprocess
import struct
from pathlib import Path
from unittest import mock


HELPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "vim4"
    / "hardware-control"
    / "scripts"
    / "vim4_hw_panel.py"
)

spec = importlib.util.spec_from_file_location("vim4_hw_panel", HELPER_PATH)
vim4_hw_panel = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vim4_hw_panel
spec.loader.exec_module(vim4_hw_panel)


class HardwarePanelStatusTest(unittest.TestCase):
    def test_path_status_reports_ready_for_existing_readable_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "node"
            path.write_text("1\n", encoding="ascii")

            status = vim4_hw_panel.path_status("LED", path)

        self.assertEqual(status.name, "LED")
        self.assertEqual(status.state, "ready")
        self.assertEqual(status.detail, str(path))

    def test_path_status_reports_missing_for_absent_path(self):
        status = vim4_hw_panel.path_status("SPI0", Path("/missing/spidev1.0"))

        self.assertEqual(status.state, "missing")
        self.assertIn("/missing/spidev1.0", status.detail)

    def test_i2c_status_explains_missing_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = vim4_hw_panel.i2c_status(5, dev_root=Path(tmp))

        self.assertEqual(status.state, "missing")
        self.assertIn("i2cm_f", status.detail)
        self.assertIn("reboot", status.detail)


class HardwarePanelRenderTest(unittest.TestCase):
    def test_read_adc_reports_raw_and_estimated_voltage(self):
        with tempfile.TemporaryDirectory() as tmp:
            iio = Path(tmp)
            (iio / "in_voltage6_raw").write_text("2048\n", encoding="ascii")

            sample = vim4_hw_panel.read_adc_sample(6, iio_device=iio)

        self.assertEqual(sample["state"], "ready")
        self.assertEqual(sample["raw"], 2048)
        self.assertIn("0.900", sample["voltage"])

    def test_render_gpio_pwm_map_is_read_only(self):
        text = vim4_hw_panel.render_gpio_pwm_map()

        self.assertIn("read-only", text.lower())
        self.assertIn("wPi", text)
        self.assertIn("ADC_CH6", text)
        self.assertNotIn("Enter GPIO", text)

    def test_render_bus_status_includes_spi_and_uart_overlay_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = vim4_hw_panel.render_bus_status(dev_root=Path(tmp))

        self.assertIn("SPI0", text)
        self.assertIn("spi0", text)
        self.assertIn("UART_E", text)
        self.assertIn("uart_e", text)


class HardwarePanelControlTest(unittest.TestCase):
    def test_set_led_brightness_rejects_value_above_max(self):
        with tempfile.TemporaryDirectory() as tmp:
            led = Path(tmp)
            (led / "max_brightness").write_text("1\n", encoding="ascii")
            (led / "brightness").write_text("0\n", encoding="ascii")

            with self.assertRaisesRegex(ValueError, "0..1"):
                vim4_hw_panel.set_led_brightness(2, led_path=led)

    def test_set_led_brightness_writes_valid_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            led = Path(tmp)
            (led / "max_brightness").write_text("3\n", encoding="ascii")
            brightness = led / "brightness"
            brightness.write_text("0\n", encoding="ascii")

            vim4_hw_panel.set_led_brightness(2, led_path=led)

            self.assertEqual(brightness.read_text(encoding="ascii"), "2\n")

    def test_run_fan_action_allows_only_skill_actions(self):
        with self.assertRaisesRegex(ValueError, "unsupported fan action"):
            vim4_hw_panel.run_fan_action("turbo")

    def test_run_fan_action_invokes_fan_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            fan_script = Path(tmp) / "fan.sh"
            fan_script.write_text("#!/bin/sh\n", encoding="ascii")
            completed = subprocess.CompletedProcess(["fan.sh", "mode"], 0, "mode=auto\n", "")
            with mock.patch.object(vim4_hw_panel.subprocess, "run", return_value=completed) as run:
                result = vim4_hw_panel.run_fan_action("mode", fan_script=fan_script)

        run.assert_called_once()
        self.assertIn("mode=auto", result)


class HardwarePanelCliTest(unittest.TestCase):
    def test_build_parser_defaults_to_key_enabled_and_oled_disabled(self):
        args = vim4_hw_panel.build_parser().parse_args([])

        self.assertFalse(args.no_key)
        self.assertFalse(args.oled)
        self.assertEqual(args.i2c_bus, 5)
        self.assertEqual(args.oled_addr, 0x3C)

    def test_func_key_status_missing_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = vim4_hw_panel.func_key_status(device=Path(tmp) / "event2")

        self.assertEqual(status.state, "missing")
        self.assertIn("adc_keypad", status.detail)

    def test_render_main_menu_contains_all_pages(self):
        menu = vim4_hw_panel.render_main_menu()

        self.assertIn("[1] Board Status", menu)
        self.assertIn("[8] Func Key Status", menu)
        self.assertIn("[q] Quit", menu)


class HardwarePanelDispatchTest(unittest.TestCase):
    def test_render_page_dispatches_known_page(self):
        text = vim4_hw_panel.render_page("5")

        self.assertIn("GPIO/PWM Map", text)

    def test_render_page_rejects_unknown_page(self):
        self.assertIn("Unknown", vim4_hw_panel.render_page("x"))

    def test_oled_summary_text_is_compact(self):
        text = vim4_hw_panel.oled_summary_text(
            cpu_percent=12.3,
            memory_percent=45.6,
            adc6="100",
            adc3="200",
        )

        self.assertIn("CPU 12%", text)
        self.assertIn("MEM 46%", text)
        self.assertLessEqual(len(text.splitlines()), 4)


class HardwarePanelOptionalIoTest(unittest.TestCase):
    def test_parse_input_event_returns_press_action(self):
        data = struct.pack(vim4_hw_panel.INPUT_EVENT_FORMAT, 1, 2, vim4_hw_panel.EV_KEY, 28, 1)

        action = vim4_hw_panel.parse_func_key_action(data)

        self.assertEqual(action, "press")

    def test_update_oled_status_reports_missing_bus_without_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            message = vim4_hw_panel.update_oled_status(
                enabled=True,
                bus=5,
                addr=0x3C,
                dev_root=Path(tmp),
            )

        self.assertIn("missing", message)
        self.assertIn("/i2c-5", message)

    def test_update_oled_status_skips_when_disabled(self):
        message = vim4_hw_panel.update_oled_status(enabled=False, bus=5, addr=0x3C)

        self.assertEqual(message, "OLED disabled")

    def test_update_oled_status_draws_summary_when_bus_exists(self):
        class FakeDisplay:
            text = ""

            def __init__(self, bus, addr, dev_root):
                self.bus = bus
                self.addr = addr
                self.dev_root = dev_root

            def init(self):
                pass

            def clear(self):
                pass

            def draw_text(self, text):
                FakeDisplay.text = text

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as tmp:
            dev_root = Path(tmp)
            (dev_root / "i2c-5").write_text("", encoding="ascii")
            message = vim4_hw_panel.update_oled_status(
                enabled=True,
                bus=5,
                addr=0x3C,
                dev_root=dev_root,
                display_cls=FakeDisplay,
            )

        self.assertEqual(message, "OLED status updated")
        self.assertIn("CPU", FakeDisplay.text)
        self.assertIn("MEM", FakeDisplay.text)

    def test_run_interactive_updates_oled_before_quit(self):
        args = vim4_hw_panel.build_parser().parse_args(["--oled"])

        with (
            mock.patch.object(vim4_hw_panel, "clear_screen"),
            mock.patch("builtins.print"),
            mock.patch.object(vim4_hw_panel, "open_func_key_for_auxiliary", return_value=None),
            mock.patch.object(vim4_hw_panel, "prompt_input", return_value="q"),
            mock.patch.object(vim4_hw_panel, "update_oled_status", return_value="OLED status updated") as update,
        ):
            result = vim4_hw_panel.run_interactive(args)

        self.assertEqual(result, 0)
        update.assert_called_once_with(True, 5, 0x3C)

    def test_open_func_key_for_auxiliary_skips_when_disabled(self):
        fd = vim4_hw_panel.open_func_key_for_auxiliary(disabled=True)

        self.assertIsNone(fd)


if __name__ == "__main__":
    unittest.main()
