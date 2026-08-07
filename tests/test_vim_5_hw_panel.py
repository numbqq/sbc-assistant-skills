import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


HELPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "vim-5"
    / "hardware-control"
    / "scripts"
    / "vim-5_hw_panel.py"
)

spec = importlib.util.spec_from_file_location("vim_5_hw_panel", HELPER_PATH)
vim_5_hw_panel = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vim_5_hw_panel
spec.loader.exec_module(vim_5_hw_panel)


class VimFiveHardwarePanelMappingTest(unittest.TestCase):
    def test_i2c_status_uses_vim_5_overlay_and_device_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            dev_root = Path(tmp)
            status = vim_5_hw_panel.i2c_status(3, dev_root=dev_root)

        self.assertEqual(status.state, "missing")
        self.assertIn("i2c_d", status.detail)
        self.assertIn("PIN22/PIN23", status.detail)
        self.assertIn("i2c-3", status.detail)
        self.assertIn("kvim-5.dtb.overlay.env", status.detail)
        self.assertIn("kvim-5.dtb.overlays", status.detail)

    def test_i2c_bus_6_uses_i2c_g(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = vim_5_hw_panel.i2c_status(6, dev_root=Path(tmp))

        self.assertIn("i2c_g", status.detail)
        self.assertIn("PIN25/PIN26", status.detail)

    def test_adc_monitor_reads_adc0_and_adc1(self):
        with tempfile.TemporaryDirectory() as tmp:
            iio = Path(tmp)
            (iio / "in_voltage0_input").write_text("2048\n", encoding="ascii")
            (iio / "in_voltage3_input").write_text("1024\n", encoding="ascii")

            sample = vim_5_hw_panel.read_adc_sample(0, iio_device=iio)
            adc1_sample = vim_5_hw_panel.read_adc_sample(1, iio_device=iio)

        self.assertEqual(sample["state"], "ready")
        self.assertEqual(sample["pin"], "PIN10")
        self.assertEqual(sample["name"], "ADC0")
        self.assertEqual(sample["iio_channel"], 0)
        self.assertEqual(sample["wpi_pin"], 19)
        self.assertEqual(sample["input"], "2048")
        self.assertEqual(adc1_sample["pin"], "PIN12")
        self.assertEqual(adc1_sample["name"], "ADC1")
        self.assertEqual(adc1_sample["iio_channel"], 3)
        self.assertEqual(adc1_sample["wpi_pin"], 20)
        self.assertEqual(adc1_sample["input"], "1024")

    def test_gpio_map_lists_vim_5_40pin_alternate_overlays(self):
        text = vim_5_hw_panel.render_gpio_pwm_map()

        self.assertIn("in_voltage0_input", text)
        self.assertIn("in_voltage3_input", text)
        self.assertIn("gpio aread 19", text)
        self.assertIn("gpio aread 20", text)
        self.assertNotIn("adc " + "single", text)
        self.assertIn("PIN.D13", text)
        self.assertIn("spdifout", text)
        self.assertIn("uart_ao_e", text)
        self.assertIn("i2c_d", text)
        self.assertIn("i2c_g", text)
        self.assertIn("spi1", text)
        self.assertIn("pwm_j", text)
        self.assertIn("IR", text)

    def test_bus_status_includes_vim_5_spi_and_uart_overlay_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = vim_5_hw_panel.render_bus_status(dev_root=Path(tmp))

        self.assertIn("I2C3", text)
        self.assertIn("I2C6", text)
        self.assertIn("SPI1", text)
        self.assertIn("spi1", text)
        self.assertIn("UART_AO_E", text)
        self.assertIn("uart_ao_e", text)

    def test_parser_defaults_oled_to_i2c3(self):
        args = vim_5_hw_panel.build_parser().parse_args([])

        self.assertEqual(args.i2c_bus, 3)
        self.assertEqual(args.oled_addr, 0x3C)

    def test_func_key_uses_vim_5_event3(self):
        self.assertEqual(vim_5_hw_panel.FUNC_KEY_DEVICE, Path("/dev/input/event3"))
        self.assertEqual(vim_5_hw_panel.FUNC_KEY_NAME, "adc_keypad")

    def test_gsensor_uses_vim_5_event0(self):
        self.assertEqual(vim_5_hw_panel.GSENSOR_DEVICE, Path("/dev/input/event0"))
        self.assertEqual(vim_5_hw_panel.GSENSOR_NAME, "kxtj3_accel")
        self.assertIn("+X=USB-A edge", vim_5_hw_panel.GSENSOR_AXIS_ORIENTATION)
        self.assertIn("+Y=left/Gsensor edge", vim_5_hw_panel.GSENSOR_AXIS_ORIENTATION)
        self.assertIn("+Z=component side up", vim_5_hw_panel.GSENSOR_AXIS_ORIENTATION)

    def test_gsensor_status_missing_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = vim_5_hw_panel.gsensor_status(device=Path(tmp) / "event0")

        self.assertEqual(status.state, "missing")
        self.assertIn("kxtj3_accel", status.detail)

    def test_expansion_board_constants_use_vim_5_paths(self):
        self.assertEqual(vim_5_hw_panel.EXPANSION_GREEN_LED_PATH, Path("/sys/class/leds/green_led"))
        self.assertEqual(vim_5_hw_panel.EXT_BOARD_CODEC_OVERLAY, "ext-board-codec")
        self.assertEqual(vim_5_hw_panel.SPI_LCD_OVERLAY, "spi1-lcd")
        self.assertEqual(vim_5_hw_panel.SPI_LCD_HELPER.name, "spi_lcd_st7735.py")
        self.assertEqual(
            vim_5_hw_panel.SPI_LCD_HELPER_REPO_PATH,
            "skills/vim-5/hardware-control/scripts/spi_lcd_st7735.py",
        )
        self.assertIn("python3-spidev", vim_5_hw_panel.SPI_LCD_DEPENDENCIES)
        self.assertEqual(vim_5_hw_panel.ANALOG_MIC_DEVICE, "hw:0,1")
        self.assertEqual(vim_5_hw_panel.MIC_ARRAY_DEVICE, "hw:0,3")

    def test_command_status_includes_install_hint_for_missing_dependency(self):
        with mock.patch.object(vim_5_hw_panel.shutil, "which", return_value=None):
            status = vim_5_hw_panel.command_status("arecord", "arecord")

        self.assertEqual(status.state, "missing")
        self.assertIn("missing command: arecord", status.detail)
        self.assertIn("sudo apt install alsa-utils", status.detail)

    def test_expansion_board_status_includes_audio_and_spi_lcd_guidance(self):
        text = vim_5_hw_panel.render_expansion_board_status()

        self.assertIn("/sys/class/leds/green_led", text)
        self.assertIn("ext-board-codec", text)
        self.assertIn("TDMIN_B source select", text)
        self.assertIn("arecord -D hw:0,1 -f cd -c 2 -d 10 test.wav", text)
        self.assertIn("arecord -Dhw:0,3 -r 48000 -f S16_LE -c 6 -d 10 pdm_6ch.wav", text)
        self.assertIn("spi1-lcd", text)
        self.assertIn("/dev/spidev1.0", text)
        self.assertIn("skills/vim-5/hardware-control/scripts/spi_lcd_st7735.py", text)
        self.assertNotIn(str(Path.home() / "sbc-assistant-skills"), text)
        self.assertIn("python3-spidev gpiod python3-libgpiod", text)
        self.assertIn("shared pins", text)

    def test_main_menu_exposes_expansion_board_status(self):
        self.assertIn("[9] Expansion Board Status", vim_5_hw_panel.render_main_menu())
        self.assertIn("Expansion Board Status", vim_5_hw_panel.render_page("9"))

    def test_main_menu_exposes_gsensor_status(self):
        self.assertIn("[10] G-Sensor Status", vim_5_hw_panel.render_main_menu())
        self.assertIn("G-Sensor Status", vim_5_hw_panel.render_page("10"))

    def test_oled_summary_uses_adc0_and_adc1_labels(self):
        text = vim_5_hw_panel.oled_summary_text(
            cpu_percent=12.3,
            memory_percent=45.6,
            adc0="100",
            adc1="200",
        )

        self.assertIn("ADC0 100", text)
        self.assertIn("ADC1 200", text)
        self.assertNotIn("ADC6", text)


if __name__ == "__main__":
    unittest.main()
