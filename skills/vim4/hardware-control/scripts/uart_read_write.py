#!/usr/bin/env python3
"""Minimal stdlib UART helper for Khadas VIM4 /dev/ttyS4."""

from __future__ import annotations

import argparse
import os
import select
import sys
import termios
import time


BAUD_NAMES = {
    9600: "B9600",
    19200: "B19200",
    38400: "B38400",
    57600: "B57600",
    115200: "B115200",
    230400: "B230400",
    460800: "B460800",
    500000: "B500000",
    576000: "B576000",
    921600: "B921600",
    1000000: "B1000000",
    1152000: "B1152000",
    1500000: "B1500000",
    2000000: "B2000000",
}


def baud_constant(baud: int) -> int:
    name = BAUD_NAMES.get(baud)
    if name is None or not hasattr(termios, name):
        supported = ", ".join(str(rate) for rate, baud_name in sorted(BAUD_NAMES.items()) if hasattr(termios, baud_name))
        raise SystemExit(f"unsupported baud {baud}; supported: {supported}")
    return getattr(termios, name)


def open_uart(device: str, baud: int) -> int:
    fd = os.open(device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    attrs = termios.tcgetattr(fd)
    speed = baud_constant(baud)

    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CLOCAL | termios.CREAD | termios.CS8
    attrs[3] = 0
    attrs[4] = speed
    attrs[5] = speed
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0

    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd


def read_for(fd: int, timeout: float) -> bytes:
    chunks: list[bytes] = []
    deadline = time.monotonic() + timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        readable, _, _ = select.select([fd], [], [], remaining)
        if not readable:
            break
        chunk = os.read(fd, 4096)
        if chunk:
            chunks.append(chunk)
    return b"".join(chunks)


def write_all(fd: int, payload: bytes) -> None:
    while payload:
        _, writable, _ = select.select([], [fd], [], 5)
        if not writable:
            raise TimeoutError("timed out waiting for UART write readiness")
        count = os.write(fd, payload)
        payload = payload[count:]
    termios.tcdrain(fd)


def cmd_send(args: argparse.Namespace) -> None:
    payload = args.text.encode(args.encoding)
    if args.newline:
        payload += b"\n"
    fd = open_uart(args.device, args.baud)
    try:
        write_all(fd, payload)
    finally:
        os.close(fd)


def cmd_receive(args: argparse.Namespace) -> None:
    fd = open_uart(args.device, args.baud)
    try:
        data = read_for(fd, args.timeout)
    finally:
        os.close(fd)
    sys.stdout.buffer.write(data)
    if data and not data.endswith(b"\n"):
        sys.stdout.buffer.write(b"\n")


def cmd_loopback(args: argparse.Namespace) -> None:
    payload = args.text.encode(args.encoding)
    if args.newline:
        payload += b"\n"
    fd = open_uart(args.device, args.baud)
    try:
        write_all(fd, payload)
        data = read_for(fd, args.timeout)
    finally:
        os.close(fd)
    sys.stdout.buffer.write(data)
    if data and not data.endswith(b"\n"):
        sys.stdout.buffer.write(b"\n")


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--device", default="/dev/ttyS4")
    parser.add_argument("--baud", type=int, default=115200)


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal UART read/write helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    send = subparsers.add_parser("send", help="write text to a UART device")
    add_common(send)
    send.add_argument("--text", required=True)
    send.add_argument("--encoding", default="utf-8")
    send.add_argument("--newline", action="store_true")
    send.set_defaults(func=cmd_send)

    receive = subparsers.add_parser("receive", help="read bytes from a UART device")
    add_common(receive)
    receive.add_argument("--timeout", type=float, default=5.0)
    receive.set_defaults(func=cmd_receive)

    loopback = subparsers.add_parser("loopback", help="write text then read response")
    add_common(loopback)
    loopback.add_argument("--text", default="hello")
    loopback.add_argument("--encoding", default="utf-8")
    loopback.add_argument("--newline", action="store_true")
    loopback.add_argument("--timeout", type=float, default=2.0)
    loopback.set_defaults(func=cmd_loopback)

    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
