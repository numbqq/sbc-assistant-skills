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
    / "spi_lcd_st7735.py"
)

spec = importlib.util.spec_from_file_location("spi_lcd_st7735", HELPER_PATH)
spi_lcd_st7735 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = spi_lcd_st7735
spec.loader.exec_module(spi_lcd_st7735)


class SpiLcdSt7735Test(unittest.TestCase):
    def test_parse_spidev_accepts_vim_5_default(self):
        self.assertEqual(spi_lcd_st7735.parse_spidev("/dev/spidev1.0"), (1, 0))

    def test_default_gpio_lines_resolve_to_vim_5_expansion_board_lines(self):
        self.assertEqual(spi_lcd_st7735.resolve_gpio_line("GPIOD_5"), ("gpiochip10", 5))
        self.assertEqual(spi_lcd_st7735.resolve_gpio_line("GPIOM_1"), ("gpiochip3", 1))
        self.assertEqual(spi_lcd_st7735.resolve_gpio_line("gpiochip10:5"), ("gpiochip10", 5))

    def test_test_frame_has_expected_size_and_nonblack_pixels(self):
        frame = spi_lcd_st7735.build_test_frame()

        self.assertEqual(len(frame), spi_lcd_st7735.WIDTH * spi_lcd_st7735.HEIGHT)
        self.assertIn(spi_lcd_st7735.WHITE, frame)
        self.assertIn(spi_lcd_st7735.BLUE, frame)

    def test_status_reports_overlay_dependencies_and_helper_defaults(self):
        args = spi_lcd_st7735.build_parser().parse_args(["status", "--spi", "/tmp/missing-spidev"])
        stream = io.StringIO()

        with (
            mock.patch.object(spi_lcd_st7735, "module_available", return_value=False),
            mock.patch.object(spi_lcd_st7735, "command_available", return_value=False),
            mock.patch.object(spi_lcd_st7735, "apt_package_installed", return_value=False),
            contextlib.redirect_stdout(stream),
        ):
            rc = spi_lcd_st7735.cmd_status(args)

        text = stream.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("required_overlay=spi1-lcd", text)
        self.assertIn("apt_dependencies=python3-spidev gpiod python3-libgpiod", text)
        self.assertIn("default_reset_line=GPIOD_5", text)
        self.assertIn("default_dc_line=GPIOM_1", text)
        self.assertIn("python_executable=", text)
        self.assertIn("apt_package_python3_spidev=missing_or_unknown", text)
        self.assertIn("missing_dependency_note=install with: sudo apt install python3-spidev", text)
        self.assertIn("missing_gpio_dependency_note=install with: sudo apt install gpiod python3-libgpiod", text)
        self.assertIn("spi_lcd_ready=no", text)

    def test_missing_spidev_note_mentions_active_python_when_apt_package_exists(self):
        with mock.patch.object(spi_lcd_st7735, "apt_package_installed", return_value=True):
            note = spi_lcd_st7735.missing_spidev_message()

        self.assertIn("python3-spidev is installed for the system Python", note)
        self.assertIn(spi_lcd_st7735.sys.executable, note)
        self.assertIn("/usr/bin/python3", note)


if __name__ == "__main__":
    unittest.main()
