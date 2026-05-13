#!/usr/bin/env python3
"""Read Khadas VIM4 ADC raw values and show calculated voltage.

VIM4 40-pin ADC mapping:
  PIN10 -> ADC_CH6 -> /sys/bus/iio/devices/iio:device0/in_voltage6_raw
  PIN12 -> ADC_CH3 -> /sys/bus/iio/devices/iio:device0/in_voltage3_raw

The ADC input range is 0 to 1.8 V. This script defaults to a 12-bit
0..4095 raw range; pass --raw-max if your kernel image reports another
full-scale raw value.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path


IIO_DEVICE = Path("/sys/bus/iio/devices/iio:device0")
CHANNELS = {
    6: {"pin": "PIN10", "name": "ADC_CH6"},
    3: {"pin": "PIN12", "name": "ADC_CH3"},
}
DEFAULT_RAW_MAX = 4095
DEFAULT_VREF = 1.8

KEEP_RUNNING = True


def stop(_signum: int, _frame: object) -> None:
    global KEEP_RUNNING
    KEEP_RUNNING = False


def channel_path(channel: int, iio_device: Path) -> Path:
    return iio_device / f"in_voltage{channel}_raw"


def parse_channel(value: str) -> int:
    try:
        channel = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ADC channel: {value}") from exc
    if channel not in CHANNELS:
        supported = ", ".join(str(item) for item in sorted(CHANNELS))
        raise argparse.ArgumentTypeError(f"unsupported ADC channel {channel}; use {supported}")
    return channel


def read_raw(path: Path) -> int:
    try:
        text = path.read_text(encoding="ascii").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"missing {path}; check that this is a VIM4 with IIO ADC exposed"
        ) from exc
    except PermissionError as exc:
        raise PermissionError(f"cannot read {path}; try running with sudo") from exc

    try:
        return int(text, 0)
    except ValueError as exc:
        raise ValueError(f"invalid raw ADC value in {path}: {text!r}") from exc


def raw_to_voltage(raw: int, raw_max: int, vref: float) -> float:
    if raw_max <= 0:
        raise ValueError("--raw-max must be greater than 0")
    if vref <= 0:
        raise ValueError("--vref must be greater than 0")
    return raw * vref / raw_max


def print_sample(channel: int, path: Path, raw: int, voltage: float) -> None:
    meta = CHANNELS[channel]
    print(
        f"channel={channel} "
        f"pin={meta['pin']} "
        f"name={meta['name']} "
        f"raw={raw} "
        f"voltage={voltage:.4f}V "
        f"path={path}",
        flush=True,
    )


def cmd_status(args: argparse.Namespace) -> int:
    print(f"iio_device={args.iio_device}")
    for channel in sorted(CHANNELS):
        path = channel_path(channel, args.iio_device)
        meta = CHANNELS[channel]
        state = "readable" if path.is_file() and path.stat().st_mode else "missing"
        print(f"channel={channel} pin={meta['pin']} name={meta['name']} state={state} path={path}")
    print(f"vref={args.vref:.4f}V")
    print(f"raw_max={args.raw_max}")
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    path = channel_path(args.channel, args.iio_device)
    raw = read_raw(path)
    voltage = raw_to_voltage(raw, args.raw_max, args.vref)
    print_sample(args.channel, path, raw, voltage)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    path = channel_path(args.channel, args.iio_device)
    count = 0
    while KEEP_RUNNING and (args.count == 0 or count < args.count):
        raw = read_raw(path)
        voltage = raw_to_voltage(raw, args.raw_max, args.vref)
        print_sample(args.channel, path, raw, voltage)
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
    parser.add_argument(
        "--vref",
        type=float,
        default=DEFAULT_VREF,
        help="ADC full-scale input voltage, default: 1.8",
    )
    parser.add_argument(
        "--raw-max",
        type=int,
        default=DEFAULT_RAW_MAX,
        help="raw full-scale value, default: 4095",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read VIM4 ADC raw values and display calculated voltage."
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
