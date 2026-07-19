#!/usr/bin/env python3
"""Read Khadas VIM 5 ADC input values.

VIM 5 40-pin ADC mapping:
  PIN10 -> ADC0 -> /sys/bus/iio/devices/iio:device0/in_voltage0_input
  PIN12 -> ADC1 -> /sys/bus/iio/devices/iio:device0/in_voltage3_input

The board adc utility exposes the same inputs as:
  adc single 0 0
  adc single 0 3
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path


IIO_DEVICE = Path("/sys/bus/iio/devices/iio:device0")
CHANNELS = {
    0: {"pin": "PIN10", "name": "ADC0", "iio_channel": 0, "adc_single": "adc single 0 0"},
    1: {"pin": "PIN12", "name": "ADC1", "iio_channel": 3, "adc_single": "adc single 0 3"},
    3: {"pin": "PIN12", "name": "ADC1", "iio_channel": 3, "adc_single": "adc single 0 3"},
}
STATUS_CHANNELS = (0, 1)

KEEP_RUNNING = True


def stop(_signum: int, _frame: object) -> None:
    global KEEP_RUNNING
    KEEP_RUNNING = False


def channel_path(channel: int, iio_device: Path) -> Path:
    meta = CHANNELS[channel]
    return iio_device / f"in_voltage{meta['iio_channel']}_input"


def parse_channel(value: str) -> int:
    try:
        channel = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ADC channel: {value}") from exc
    if channel not in CHANNELS:
        supported = ", ".join(str(item) for item in sorted(CHANNELS))
        raise argparse.ArgumentTypeError(f"unsupported ADC channel {channel}; use {supported}")
    return channel


def read_input(path: Path) -> str:
    try:
        text = path.read_text(encoding="ascii").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"missing {path}; check that this is a VIM 5 with IIO ADC exposed"
        ) from exc
    except PermissionError as exc:
        raise PermissionError(f"cannot read {path}; try running with sudo") from exc
    return text


def print_sample(channel: int, path: Path, input_value: str) -> None:
    meta = CHANNELS[channel]
    print(
        f"channel={channel} "
        f"pin={meta['pin']} "
        f"name={meta['name']} "
        f"iio_channel={meta['iio_channel']} "
        f"adc_command='{meta['adc_single']}' "
        f"input={input_value} "
        f"path={path}",
        flush=True,
    )


def cmd_status(args: argparse.Namespace) -> int:
    print(f"iio_device={args.iio_device}")
    for channel in STATUS_CHANNELS:
        path = channel_path(channel, args.iio_device)
        meta = CHANNELS[channel]
        state = "readable" if path.is_file() and path.stat().st_mode else "missing"
        print(
            f"channel={channel} pin={meta['pin']} name={meta['name']} "
            f"iio_channel={meta['iio_channel']} adc_command='{meta['adc_single']}' "
            f"state={state} path={path}"
        )
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    path = channel_path(args.channel, args.iio_device)
    input_value = read_input(path)
    print_sample(args.channel, path, input_value)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    path = channel_path(args.channel, args.iio_device)
    count = 0
    while KEEP_RUNNING and (args.count == 0 or count < args.count):
        input_value = read_input(path)
        print_sample(args.channel, path, input_value)
        count += 1
        if KEEP_RUNNING and (args.count == 0 or count < args.count):
            time.sleep(args.interval)
    return 0


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--iio-device",
        type=Path,
        default=IIO_DEVICE,
        help=f"IIO device directory, default: {IIO_DEVICE}",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read VIM 5 ADC input values."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="show supported ADC sysfs files")
    add_common_args(status_parser)
    status_parser.set_defaults(func=cmd_status)

    read_parser = subparsers.add_parser("read", help="read one ADC sample")
    add_common_args(read_parser)
    read_parser.add_argument("channel", type=parse_channel, choices=sorted(CHANNELS))
    read_parser.set_defaults(func=cmd_read)

    watch_parser = subparsers.add_parser("watch", help="read ADC samples repeatedly")
    add_common_args(watch_parser)
    watch_parser.add_argument("channel", type=parse_channel, choices=sorted(CHANNELS))
    watch_parser.add_argument("--interval", type=float, default=1.0, help="seconds between samples")
    watch_parser.add_argument("--count", type=int, default=0, help="number of samples, 0 means forever")
    watch_parser.set_defaults(func=cmd_watch)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
