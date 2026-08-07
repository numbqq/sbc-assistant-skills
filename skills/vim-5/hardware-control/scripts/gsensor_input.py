#!/usr/bin/env python3
from __future__ import annotations

import argparse
import array
import fcntl
import json
import os
import select
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path


GSENSOR_DEVICE = Path("/dev/input/event0")
GSENSOR_DEVICE_NAME = "kxtj3_accel"

EV_SYN = 0x00
EV_ABS = 0x03
SYN_REPORT = 0x00
ABS_X = 0x00
ABS_Y = 0x01
ABS_Z = 0x02
AXIS_NAMES = {
    ABS_X: "x",
    ABS_Y: "y",
    ABS_Z: "z",
}
AXIS_ORIENTATION = {
    "x": {"positive": "USB-A_edge", "negative": "HDMI_IN_edge"},
    "y": {"positive": "left_Gsensor_edge", "negative": "right_USB-A_2_0_edge"},
    "z": {"positive": "component_side_up", "negative": "board_back_side"},
}
AXIS_ORIENTATION_REFERENCE = "top_view_USB-A_edge_at_top_HDMI_IN_edge_at_bottom_Gsensor_near_left_edge"
INPUT_EVENT_FORMAT = "llHHi"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FORMAT)


@dataclass(frozen=True)
class InputEvent:
    seconds: int
    microseconds: int
    event_type: int
    code: int
    value: int
    axis: str | None


@dataclass(frozen=True)
class AccelSample:
    seconds: int
    microseconds: int
    axes: dict[str, int]


def parse_input_event(data: bytes) -> InputEvent:
    if len(data) != INPUT_EVENT_SIZE:
        raise ValueError(f"expected {INPUT_EVENT_SIZE}-byte input_event, got {len(data)} bytes")

    seconds, microseconds, event_type, code, value = struct.unpack(INPUT_EVENT_FORMAT, data)
    axis = AXIS_NAMES.get(code) if event_type == EV_ABS else None
    return InputEvent(seconds, microseconds, event_type, code, value, axis)


def eviocgname_request(length: int) -> int:
    return 0x80000000 | (length << 16) | (ord("E") << 8) | 0x06


def device_name(fd: int) -> str:
    length = 256
    buf = array.array("b", [0] * length)
    try:
        fcntl.ioctl(fd, eviocgname_request(length), buf, True)
    except OSError:
        return ""
    raw = buf.tobytes().split(b"\0", 1)[0]
    return raw.decode("utf-8", errors="replace")


def open_gsensor_device(device: Path) -> int:
    return os.open(device, os.O_RDONLY | os.O_NONBLOCK)


def print_axis_orientation() -> None:
    print(f"axis_orientation_reference={AXIS_ORIENTATION_REFERENCE}")
    for axis in ("x", "y", "z"):
        orientation = AXIS_ORIENTATION[axis]
        print(f"axis_{axis}_positive={orientation['positive']}")
        print(f"axis_{axis}_negative={orientation['negative']}")


def print_status(device: Path, expected_name: str) -> int:
    print(f"accelerometer=G-sensor")
    print(f"device={device}")
    print(f"expected_name={expected_name}")
    print("axis_codes=x:ABS_X(0),y:ABS_Y(1),z:ABS_Z(2)")
    print_axis_orientation()
    print("units=raw input-event values")

    if not device.exists():
        print("gsensor_ready=no")
        print(f"note=missing {device}")
        return 1

    try:
        fd = open_gsensor_device(device)
    except PermissionError:
        print("gsensor_ready=no")
        print(f"note=permission denied reading {device}; run with sudo or add the user to the input group")
        return 1
    except OSError as exc:
        print("gsensor_ready=no")
        print(f"note=cannot open {device}: {exc}")
        return 1

    try:
        name = device_name(fd)
        print(f"name={name or 'unknown'}")
        if name == expected_name:
            print("gsensor_ready=yes")
            return 0
        print("gsensor_ready=no")
        print(f"note={device} is not {expected_name}")
        return 1
    finally:
        os.close(fd)


def read_next_accel_sample(fd: int, timeout: float | None) -> AccelSample | None:
    deadline = None if timeout is None else time.monotonic() + timeout
    axes: dict[str, int] = {}
    timestamp = (0, 0)

    while True:
        wait = None
        if deadline is not None:
            wait = max(0.0, deadline - time.monotonic())
            if wait == 0.0:
                return None

        ready, _, _ = select.select([fd], [], [], wait)
        if not ready:
            return None

        try:
            data = os.read(fd, INPUT_EVENT_SIZE)
        except BlockingIOError:
            continue
        if not data:
            return None

        event = parse_input_event(data)
        if event.axis is not None:
            axes[event.axis] = event.value
            timestamp = (event.seconds, event.microseconds)
            continue

        if event.event_type == EV_SYN and event.code == SYN_REPORT and all(axis in axes for axis in ("x", "y", "z")):
            return AccelSample(event.seconds, event.microseconds, dict(axes))

        if all(axis in axes for axis in ("x", "y", "z")) and timestamp != (0, 0):
            seconds, microseconds = timestamp
            return AccelSample(seconds, microseconds, dict(axes))


def format_sample(sample: AccelSample, json_output: bool = False) -> str:
    payload = {
        "time": f"{sample.seconds}.{sample.microseconds:06d}",
        "x": sample.axes["x"],
        "y": sample.axes["y"],
        "z": sample.axes["z"],
        "units": "raw",
    }
    if json_output:
        return json.dumps(payload, separators=(",", ":"))
    return (
        f"time={payload['time']} "
        f"x={payload['x']} y={payload['y']} z={payload['z']} units={payload['units']}"
    )


def ensure_expected_device(fd: int, device: Path, expected_name: str) -> None:
    name = device_name(fd)
    if name != expected_name:
        raise RuntimeError(f"{device} name is {name or 'unknown'}, expected {expected_name}")


def wait_for_sample(device: Path, expected_name: str, timeout: float, json_output: bool) -> int:
    try:
        fd = open_gsensor_device(device)
    except PermissionError as exc:
        raise RuntimeError(f"permission denied reading {device}; run with sudo or add the user to the input group") from exc
    except OSError as exc:
        raise RuntimeError(f"cannot open {device}: {exc}") from exc

    try:
        ensure_expected_device(fd, device, expected_name)
        sample = read_next_accel_sample(fd, timeout)
        if sample is None:
            raise TimeoutError(f"no G-sensor sample within {timeout:g}s")
        print(format_sample(sample, json_output))
        return 0
    finally:
        os.close(fd)


def listen_for_samples(device: Path, expected_name: str, count: int | None, json_output: bool) -> int:
    try:
        fd = open_gsensor_device(device)
    except PermissionError as exc:
        raise RuntimeError(f"permission denied reading {device}; run with sudo or add the user to the input group") from exc
    except OSError as exc:
        raise RuntimeError(f"cannot open {device}: {exc}") from exc

    printed = 0
    try:
        ensure_expected_device(fd, device, expected_name)
        while count is None or printed < count:
            sample = read_next_accel_sample(fd, None)
            if sample is None:
                continue
            print(format_sample(sample, json_output), flush=True)
            printed += 1
        return 0
    finally:
        os.close(fd)


def positive_int(value: str) -> int:
    parsed = int(value, 0)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be a positive integer")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read the Khadas VIM 5 G-sensor from /dev/input/event0.")
    parser.add_argument("--device", type=Path, default=GSENSOR_DEVICE, help="Input event device. Default: /dev/input/event0.")
    parser.add_argument("--expected-name", default=GSENSOR_DEVICE_NAME, help="Expected input device name. Default: kxtj3_accel.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Check the G-sensor input device.")

    sample_parser = subparsers.add_parser("sample", help="Read one x/y/z sample.")
    sample_parser.add_argument("--timeout", type=float, default=5.0, help="Seconds to wait. Default: 5.")
    sample_parser.add_argument("--json", action="store_true", help="Print one compact JSON object.")

    listen_parser = subparsers.add_parser("listen", help="Print x/y/z samples until interrupted.")
    listen_parser.add_argument("--count", type=positive_int, help="Stop after this many samples.")
    listen_parser.add_argument("--json", action="store_true", help="Print compact JSON lines.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            return print_status(args.device, args.expected_name)
        if args.command == "sample":
            return wait_for_sample(args.device, args.expected_name, args.timeout, args.json)
        if args.command == "listen":
            return listen_for_samples(args.device, args.expected_name, args.count, args.json)
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("", file=sys.stderr)
        return 130
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    parser.error(f"unknown command: {args.command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
