#!/usr/bin/env python3
"""
Minimal UART_E communication helper for Khadas VIM4.

Default UART_E device:
  /dev/ttyS4

VIM4 40-pin header UART_E pins:
  PIN15 = RX
  PIN16 = TX
"""

import argparse
import os
import select
import sys
import termios
import time


DEFAULT_DEVICE = "/dev/ttyS4"
DEFAULT_BAUD = 115200


def baud_constant(baud: int) -> int:
    name = f"B{baud}"
    value = getattr(termios, name, None)
    if value is None:
        supported = [
            item[1:]
            for item in dir(termios)
            if item.startswith("B") and item[1:].isdigit()
        ]
        raise ValueError(
            f"unsupported baud rate: {baud}. "
            f"Supported by this Python termios: {', '.join(sorted(supported, key=int))}"
        )
    return value


def open_uart(device: str, baud: int) -> int:
    if not os.path.exists(device):
        raise FileNotFoundError(
            f"{device} does not exist. On VIM4 UART_E needs the uart_e overlay enabled "
            "and a reboot before /dev/ttyS4 appears."
        )

    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    speed = baud_constant(baud)

    attrs = termios.tcgetattr(fd)

    # 8N1, raw input/output, no flow control.
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CLOCAL | termios.CREAD | termios.CS8
    attrs[3] = 0
    attrs[4] = speed
    attrs[5] = speed
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0

    if hasattr(termios, "CRTSCTS"):
        attrs[2] &= ~termios.CRTSCTS

    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


def parse_hex(hex_text: str) -> bytes:
    cleaned = hex_text.replace("0x", "").replace("0X", "")
    cleaned = "".join(cleaned.split())
    if len(cleaned) % 2:
        raise ValueError("hex data must contain an even number of hex digits")
    return bytes.fromhex(cleaned)


def printable(data: bytes, show_hex: bool) -> str:
    if show_hex:
        return data.hex(" ")
    return data.decode("utf-8", errors="replace")


def send_data(args: argparse.Namespace) -> int:
    if args.hex is not None:
        payload = parse_hex(args.hex)
    else:
        payload = args.text.encode(args.encoding)

    if args.newline:
        payload += b"\n"

    fd = open_uart(args.device, args.baud)
    try:
        os.write(fd, payload)
        termios.tcdrain(fd)
    finally:
        os.close(fd)

    print(f"sent {len(payload)} bytes")
    return 0


def receive_data(args: argparse.Namespace) -> int:
    fd = open_uart(args.device, args.baud)
    deadline = None if args.timeout <= 0 else time.monotonic() + args.timeout

    print(
        f"listening on {args.device} at {args.baud} baud "
        f"({'until Ctrl-C' if deadline is None else f'for {args.timeout:g}s'})",
        file=sys.stderr,
    )

    try:
        while True:
            if deadline is None:
                wait = 0.5
            else:
                wait = max(0.0, min(0.5, deadline - time.monotonic()))
                if wait == 0.0:
                    break

            readable, _, _ = select.select([fd], [], [], wait)
            if not readable:
                continue

            data = os.read(fd, args.chunk_size)
            if not data:
                continue

            line = printable(data, args.show_hex)
            if args.timestamp:
                line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {line}"

            print(line, end="" if not args.show_hex else "\n", flush=True)
    except KeyboardInterrupt:
        print("", file=sys.stderr)
    finally:
        os.close(fd)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send and receive UART data on Khadas VIM4 UART_E."
    )
    parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE,
        help=f"TTY device path, default: {DEFAULT_DEVICE}",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=DEFAULT_BAUD,
        help=f"baud rate, default: {DEFAULT_BAUD}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    send = subparsers.add_parser("send", help="send data once")
    send.add_argument("text", nargs="?", default="", help="text to send")
    send.add_argument("--hex", help="hex bytes to send, for example: '01 03 00 00'")
    send.add_argument(
        "--encoding",
        default="utf-8",
        help="text encoding when sending text, default: utf-8",
    )
    send.add_argument(
        "--newline",
        action="store_true",
        help="append LF after text or hex payload",
    )
    send.set_defaults(func=send_data)

    receive = subparsers.add_parser("receive", aliases=["listen"], help="listen for data")
    receive.add_argument(
        "--timeout",
        type=float,
        default=0,
        help="seconds to listen; 0 means listen until Ctrl-C, default: 0",
    )
    receive.add_argument(
        "--chunk-size",
        type=int,
        default=256,
        help="max bytes per read, default: 256",
    )
    receive.add_argument(
        "--hex",
        dest="show_hex",
        action="store_true",
        help="print received bytes as hex",
    )
    receive.add_argument(
        "--timestamp",
        action="store_true",
        help="prefix received chunks with local timestamp",
    )
    receive.set_defaults(func=receive_data)

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
