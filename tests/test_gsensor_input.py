import importlib.util
import io
import os
import struct
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock


HELPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "vim-5"
    / "hardware-control"
    / "scripts"
    / "gsensor_input.py"
)

spec = importlib.util.spec_from_file_location("gsensor_input", HELPER_PATH)
gsensor_input = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gsensor_input
spec.loader.exec_module(gsensor_input)


def pack_event(event_type, code, value, seconds=1, microseconds=2):
    return struct.pack(gsensor_input.INPUT_EVENT_FORMAT, seconds, microseconds, event_type, code, value)


class GsensorInputTest(unittest.TestCase):
    def test_parse_abs_axis_event(self):
        event = gsensor_input.parse_input_event(pack_event(gsensor_input.EV_ABS, gsensor_input.ABS_X, -123))

        self.assertEqual(event.event_type, gsensor_input.EV_ABS)
        self.assertEqual(event.code, gsensor_input.ABS_X)
        self.assertEqual(event.value, -123)
        self.assertEqual(event.axis, "x")

    def test_parse_ignores_non_axis_event(self):
        event = gsensor_input.parse_input_event(pack_event(gsensor_input.EV_SYN, gsensor_input.SYN_REPORT, 0))

        self.assertIsNone(event.axis)

    def test_parse_rejects_short_event(self):
        with self.assertRaisesRegex(ValueError, "input_event"):
            gsensor_input.parse_input_event(b"short")

    def test_eviocgname_request_includes_buffer_length(self):
        self.assertEqual(gsensor_input.eviocgname_request(256), 0x81004506)

    def test_read_next_accel_sample_collects_xyz(self):
        read_fd, write_fd = os.pipe()
        try:
            os.write(
                write_fd,
                b"".join(
                    [
                        pack_event(gsensor_input.EV_ABS, gsensor_input.ABS_X, -1),
                        pack_event(gsensor_input.EV_ABS, gsensor_input.ABS_Y, 2),
                        pack_event(gsensor_input.EV_ABS, gsensor_input.ABS_Z, 1024),
                        pack_event(gsensor_input.EV_SYN, gsensor_input.SYN_REPORT, 0),
                    ]
                ),
            )
            sample = gsensor_input.read_next_accel_sample(read_fd, timeout=0.1)
        finally:
            os.close(read_fd)
            os.close(write_fd)

        self.assertIsNotNone(sample)
        self.assertEqual(sample.axes, {"x": -1, "y": 2, "z": 1024})

    def test_format_sample_outputs_raw_units(self):
        sample = gsensor_input.AccelSample(1, 2, {"x": -1, "y": 2, "z": 1024})

        text = gsensor_input.format_sample(sample)

        self.assertIn("x=-1", text)
        self.assertIn("y=2", text)
        self.assertIn("z=1024", text)
        self.assertIn("units=raw", text)

    def test_axis_orientation_is_machine_readable(self):
        self.assertEqual(gsensor_input.AXIS_ORIENTATION["x"]["positive"], "USB-A_edge")
        self.assertEqual(gsensor_input.AXIS_ORIENTATION["x"]["negative"], "HDMI_IN_edge")
        self.assertEqual(gsensor_input.AXIS_ORIENTATION["y"]["positive"], "left_Gsensor_edge")
        self.assertEqual(gsensor_input.AXIS_ORIENTATION["y"]["negative"], "right_USB-A_2_0_edge")
        self.assertEqual(gsensor_input.AXIS_ORIENTATION["z"]["positive"], "component_side_up")
        self.assertEqual(gsensor_input.AXIS_ORIENTATION["z"]["negative"], "board_back_side")

    def test_main_returns_130_without_traceback_on_keyboard_interrupt(self):
        with mock.patch.object(gsensor_input, "listen_for_samples", side_effect=KeyboardInterrupt):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                self.assertEqual(gsensor_input.main(["listen"]), 130)
            self.assertEqual(stderr.getvalue(), "\n")


if __name__ == "__main__":
    unittest.main()
