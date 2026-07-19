#!/usr/bin/env python3
import argparse
import array
import fcntl
import os
import select
import struct
import sys
import time
from dataclasses import dataclass


FUNC_KEY_DEVICE = "/dev/input/event3"
FUNC_KEY_DEVICE_NAME = "adc_keypad"

EV_KEY = 0x01
INPUT_EVENT_FORMAT = "llHHi"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FORMAT)


@dataclass(frozen=True)
class InputEvent:
    seconds: int
    microseconds: int
    event_type: int
    code: int
    value: int
    action: str | None


def action_for_key_value(value):
    return {
        0: "release",
        1: "press",
        2: "repeat",
    }.get(value)


def parse_input_event(data):
    if len(data) != INPUT_EVENT_SIZE:
        raise ValueError(f"expected {INPUT_EVENT_SIZE}-byte input_event, got {len(data)} bytes")

    seconds, microseconds, event_type, code, value = struct.unpack(INPUT_EVENT_FORMAT, data)
    action = action_for_key_value(value) if event_type == EV_KEY else None
    return InputEvent(seconds, microseconds, event_type, code, value, action)


def eviocgname_request(length):
    return 0x80000000 | (length << 16) | (ord("E") << 8) | 0x06


def device_name(fd):
    length = 256
    buf = array.array("b", [0] * length)
    try:
        fcntl.ioctl(fd, eviocgname_request(length), buf, True)
    except OSError:
        return ""
    raw = buf.tobytes().split(b"\0", 1)[0]
    return raw.decode("utf-8", errors="replace")


def open_func_key_device():
    return os.open(FUNC_KEY_DEVICE, os.O_RDONLY | os.O_NONBLOCK)


def print_status():
    print(f"device={FUNC_KEY_DEVICE}")
    print(f"expected_name={FUNC_KEY_DEVICE_NAME}")

    if not os.path.exists(FUNC_KEY_DEVICE):
        print("key_ready=no")
        print(f"note=missing {FUNC_KEY_DEVICE}")
        return 1

    try:
        fd = open_func_key_device()
    except PermissionError:
        print("key_ready=no")
        print(f"note=permission denied reading {FUNC_KEY_DEVICE}; run with sudo or add the user to the input group")
        return 1
    except OSError as exc:
        print("key_ready=no")
        print(f"note=cannot open {FUNC_KEY_DEVICE}: {exc}")
        return 1

    try:
        name = device_name(fd)
        print(f"name={name or 'unknown'}")
        if name == FUNC_KEY_DEVICE_NAME:
            print("key_ready=yes")
            return 0
        print("key_ready=no")
        print(f"note={FUNC_KEY_DEVICE} is not {FUNC_KEY_DEVICE_NAME}")
        return 1
    finally:
        os.close(fd)


def read_next_key_event(fd, timeout):
    deadline = None if timeout is None else time.monotonic() + timeout

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

        event = parse_input_event(data)
        if event.action is not None:
            return event


def format_event(event):
    timestamp = f"{event.seconds}.{event.microseconds:06d}"
    return f"time={timestamp} key=FUNC code={event.code} action={event.action} value={event.value}"


def ensure_expected_device(fd):
    name = device_name(fd)
    if name != FUNC_KEY_DEVICE_NAME:
        raise RuntimeError(f"{FUNC_KEY_DEVICE} name is {name or 'unknown'}, expected {FUNC_KEY_DEVICE_NAME}")


def wait_for_key(timeout):
    try:
        fd = open_func_key_device()
    except PermissionError as exc:
        raise RuntimeError(f"permission denied reading {FUNC_KEY_DEVICE}; run with sudo or add the user to the input group") from exc
    except OSError as exc:
        raise RuntimeError(f"cannot open {FUNC_KEY_DEVICE}: {exc}") from exc

    try:
        ensure_expected_device(fd)
        event = read_next_key_event(fd, timeout)
        if event is None:
            raise TimeoutError(f"no Func key event within {timeout:g}s")
        print(format_event(event))
        return 0
    finally:
        os.close(fd)


def listen_for_key():
    try:
        fd = open_func_key_device()
    except PermissionError as exc:
        raise RuntimeError(f"permission denied reading {FUNC_KEY_DEVICE}; run with sudo or add the user to the input group") from exc
    except OSError as exc:
        raise RuntimeError(f"cannot open {FUNC_KEY_DEVICE}: {exc}") from exc

    try:
        ensure_expected_device(fd)
        while True:
            event = read_next_key_event(fd, None)
            if event is not None:
                print(format_event(event), flush=True)
    finally:
        os.close(fd)


def build_parser():
    parser = argparse.ArgumentParser(description="Read the Khadas VIM 5 Func key from /dev/input/event3.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Check the Func key input device.")

    wait_parser = subparsers.add_parser("wait", help="Wait for one Func key event.")
    wait_parser.add_argument("--timeout", type=float, default=10.0, help="Seconds to wait. Default: 10.")

    subparsers.add_parser("listen", help="Print Func key events until interrupted.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "status":
            return print_status()
        if args.command == "wait":
            return wait_for_key(args.timeout)
        if args.command == "listen":
            return listen_for_key()
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
