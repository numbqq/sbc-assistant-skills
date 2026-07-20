#!/usr/bin/env python3
"""Blink a VIM 5 sysfs LED continuously: on for 100 ms, off for 100 ms."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


LED_PATH = Path("/sys/class/leds/pwmled")
DEFAULT_DELAY = 0.1


def read_int(path: Path) -> int:
    return int(path.read_text(encoding="ascii").strip(), 0)


def write_brightness(led_path: Path, value: int) -> None:
    (led_path / "brightness").write_text(f"{value}\n", encoding="ascii")


def blink_forever(led_path: Path, delay: float) -> None:
    if not led_path.is_dir():
        raise FileNotFoundError(f"missing LED path: {led_path}")

    max_brightness = read_int(led_path / "max_brightness")
    if max_brightness <= 0:
        raise ValueError(f"invalid max_brightness: {max_brightness}")

    while True:
        write_brightness(led_path, max_brightness)
        time.sleep(delay)
        write_brightness(led_path, 0)
        time.sleep(delay)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Blink a VIM 5 sysfs LED continuously.")
    parser.add_argument(
        "--led-path",
        type=Path,
        default=LED_PATH,
        help=f"LED sysfs path, default: {LED_PATH}",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        help="seconds for each state, default: 0.1",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.delay < 0:
        print("error: --delay must be non-negative", file=sys.stderr)
        return 1

    try:
        blink_forever(args.led_path, args.delay)
    except KeyboardInterrupt:
        try:
            write_brightness(args.led_path, 0)
        except OSError:
            pass
        print("", file=sys.stderr)
        return 130
    except PermissionError as exc:
        print(f"error: permission denied writing LED brightness; try sudo: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
