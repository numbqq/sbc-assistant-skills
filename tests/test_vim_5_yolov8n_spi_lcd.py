import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LCD_MODULE_PATH = ROOT / "skills" / "vim-5" / "npu" / "scripts" / "vim_5_yolov8n_spi_lcd.py"

spec = importlib.util.spec_from_file_location("vim_5_yolov8n_spi_lcd", LCD_MODULE_PATH)
vim_5_yolov8n_spi_lcd = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vim_5_yolov8n_spi_lcd
spec.loader.exec_module(vim_5_yolov8n_spi_lcd)


class VimFiveYolov8nSpiLcdTest(unittest.TestCase):
    def test_state_from_detections_sorts_by_frame_position_and_limits_items(self):
        detections = [
            {"class_name": "car", "confidence": 0.7, "bbox": [80, 0, 100, 20]},
            {"class_name": "person", "confidence": 0.9, "bbox": [10, 0, 30, 20]},
            {"class_name": "cell phone", "confidence": 0.6, "bbox": [150, 0, 170, 20]},
        ]

        state = vim_5_yolov8n_spi_lcd.state_from_detections(detections, frame_width=200, max_items=2)

        self.assertEqual(state.total_count, 3)
        self.assertEqual([item.label for item in state.items], ["person", "car"])
        self.assertEqual([item.icon for item in state.items], ["person", "vehicle"])
        self.assertEqual(vim_5_yolov8n_spi_lcd.lcd_state_summary(state), "PER,CAR,+1")

    def test_render_lcd_frame_uses_repo_spi_lcd_helper_without_opening_hardware(self):
        helper = vim_5_yolov8n_spi_lcd.load_lcd_helper()
        state = vim_5_yolov8n_spi_lcd.LcdState(
            (
                vim_5_yolov8n_spi_lcd.LcdItem("person", "person", 0.92, 0.2),
                vim_5_yolov8n_spi_lcd.LcdItem("screen", "cell phone", 0.81, 0.8),
            ),
            total_count=2,
        )

        pixels = vim_5_yolov8n_spi_lcd.render_lcd_frame(helper, state)

        self.assertEqual(len(pixels), vim_5_yolov8n_spi_lcd.WIDTH * vim_5_yolov8n_spi_lcd.HEIGHT)
        self.assertGreater(len(set(pixels)), 1)
        self.assertTrue(vim_5_yolov8n_spi_lcd.loaded_lcd_helper_path().is_file())


if __name__ == "__main__":
    unittest.main()
