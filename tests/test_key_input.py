import importlib.util
import io
import struct
import sys
import unittest
from contextlib import redirect_stderr
from unittest import mock
from pathlib import Path


HELPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "vim4"
    / "hardware-control"
    / "scripts"
    / "key_input.py"
)

spec = importlib.util.spec_from_file_location("key_input", HELPER_PATH)
key_input = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = key_input
spec.loader.exec_module(key_input)


def pack_event(event_type, code, value, seconds=1, microseconds=2):
    return struct.pack(key_input.INPUT_EVENT_FORMAT, seconds, microseconds, event_type, code, value)


class KeyInputTest(unittest.TestCase):
    def test_parse_key_press_event(self):
        event = key_input.parse_input_event(pack_event(key_input.EV_KEY, 28, 1))

        self.assertEqual(event.event_type, key_input.EV_KEY)
        self.assertEqual(event.code, 28)
        self.assertEqual(event.value, 1)
        self.assertEqual(event.action, "press")

    def test_parse_ignores_non_key_event(self):
        event = key_input.parse_input_event(pack_event(0, 0, 0))

        self.assertIsNone(event.action)

    def test_parse_rejects_short_event(self):
        with self.assertRaisesRegex(ValueError, "input_event"):
            key_input.parse_input_event(b"short")

    def test_eviocgname_request_includes_buffer_length(self):
        self.assertEqual(key_input.eviocgname_request(256), 0x81004506)

    def test_main_returns_130_without_traceback_on_keyboard_interrupt(self):
        with mock.patch.object(key_input, "listen_for_key", side_effect=KeyboardInterrupt):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                self.assertEqual(key_input.main(["listen"]), 130)
            self.assertEqual(stderr.getvalue(), "\n")


if __name__ == "__main__":
    unittest.main()
