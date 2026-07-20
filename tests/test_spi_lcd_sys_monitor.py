import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path
from unittest import mock


HELPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "vim-5"
    / "hardware-control"
    / "scripts"
    / "spi_lcd_sys_monitor.py"
)

spec = importlib.util.spec_from_file_location("spi_lcd_sys_monitor", HELPER_PATH)
spi_lcd_sys_monitor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = spi_lcd_sys_monitor
spec.loader.exec_module(spi_lcd_sys_monitor)


class DummyHelper:
    @staticmethod
    def module_available(name: str) -> bool:
        return False

    @staticmethod
    def command_available(name: str) -> bool:
        return False

    @staticmethod
    def apt_package_installed(package: str) -> bool:
        return False

    @staticmethod
    def missing_spidev_message() -> str:
        return "install with: sudo apt install python3-spidev"


class SpiLcdSysMonitorTest(unittest.TestCase):
    def test_render_frame_produces_full_screen_pixel_buffer(self):
        frame = spi_lcd_sys_monitor.render_frame(
            "VIM5 SYS",
            cpu=37.5,
            mem_used_mib=2048.0,
            mem_total_mib=4096.0,
            temp_c=53.2,
        )

        self.assertEqual(len(frame), spi_lcd_sys_monitor.WIDTH * spi_lcd_sys_monitor.HEIGHT)
        self.assertIn(spi_lcd_sys_monitor.CYAN, frame)
        self.assertIn(spi_lcd_sys_monitor.WHITE, frame)

    def test_status_reports_interpreter_and_dependency_hints(self):
        args = spi_lcd_sys_monitor.build_parser().parse_args(["--status", "--spi", "/tmp/missing-spi"])
        stream = io.StringIO()

        with (
            mock.patch.object(spi_lcd_sys_monitor, "get_helper", return_value=DummyHelper()),
            mock.patch.object(spi_lcd_sys_monitor, "probe_cpu_temperature", return_value=("fan.sh temp", 48.2)),
            contextlib.redirect_stdout(stream),
        ):
            spi_lcd_sys_monitor.print_status(args)

        text = stream.getvalue()
        self.assertIn("display=ST7735_160x80", text)
        self.assertIn("python_executable=", text)
        self.assertIn("helper_path=", text)
        self.assertIn("missing_dependency_note=install with: sudo apt install python3-spidev", text)
        self.assertIn("missing_gpio_dependency_note=install with: sudo apt install gpiod python3-libgpiod", text)
        self.assertIn("spi_lcd_ready=no", text)

    def test_missing_gpio_note_mentions_active_python_when_packages_exist(self):
        helper = DummyHelper()

        with mock.patch.object(DummyHelper, "apt_package_installed", return_value=True):
            note = spi_lcd_sys_monitor.missing_gpio_note(helper)

        self.assertIn("system Python", note)
        self.assertIn(sys.executable, note)
        self.assertIn("/usr/bin/python3", note)


if __name__ == "__main__":
    unittest.main()
