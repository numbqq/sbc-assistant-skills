#!/usr/bin/env python3
"""Minimal Linux spidev helper for Khadas VIM4 SPI0."""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import os
import struct
import sys
from typing import Iterable


SPI_DEVICE = "/dev/spidev1.0"

IOC_NRBITS = 8
IOC_TYPEBITS = 8
IOC_SIZEBITS = 14

IOC_NRSHIFT = 0
IOC_TYPESHIFT = IOC_NRSHIFT + IOC_NRBITS
IOC_SIZESHIFT = IOC_TYPESHIFT + IOC_TYPEBITS
IOC_DIRSHIFT = IOC_SIZESHIFT + IOC_SIZEBITS

IOC_WRITE = 1
IOC_READ = 2

SPI_IOC_MAGIC = ord("k")


def _ioc(direction: int, type_: int, number: int, size: int) -> int:
    return (
        (direction << IOC_DIRSHIFT)
        | (type_ << IOC_TYPESHIFT)
        | (number << IOC_NRSHIFT)
        | (size << IOC_SIZESHIFT)
    )


def _ior(number: int, size: int) -> int:
    return _ioc(IOC_READ, SPI_IOC_MAGIC, number, size)


def _iow(number: int, size: int) -> int:
    return _ioc(IOC_WRITE, SPI_IOC_MAGIC, number, size)


SPI_IOC_RD_MODE = _ior(1, 1)
SPI_IOC_WR_MODE = _iow(1, 1)
SPI_IOC_RD_BITS_PER_WORD = _ior(3, 1)
SPI_IOC_WR_BITS_PER_WORD = _iow(3, 1)
SPI_IOC_RD_MAX_SPEED_HZ = _ior(4, 4)
SPI_IOC_WR_MAX_SPEED_HZ = _iow(4, 4)

# struct spi_ioc_transfer on 64-bit Linux:
# tx_buf, rx_buf, len, speed_hz, delay_usecs, bits_per_word, cs_change,
# tx_nbits, rx_nbits, word_delay_usecs, pad
TRANSFER_STRUCT = "QQIIHBBBBBB"
TRANSFER_SIZE = struct.calcsize(TRANSFER_STRUCT)
SPI_IOC_MESSAGE_1 = _iow(0, TRANSFER_SIZE)


def parse_byte(value: str) -> int:
    try:
        parsed = int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid byte: {value}") from exc
    if not 0 <= parsed <= 0xFF:
        raise argparse.ArgumentTypeError(f"byte out of range 0..255: {value}")
    return parsed


def format_bytes(values: Iterable[int]) -> str:
    return " ".join(f"0x{value:02x}" for value in values)


def get_u8(fd: int, request: int) -> int:
    buf = bytearray(1)
    fcntl.ioctl(fd, request, buf, True)
    return buf[0]


def set_u8(fd: int, request: int, value: int) -> None:
    fcntl.ioctl(fd, request, struct.pack("B", value))


def get_u32(fd: int, request: int) -> int:
    buf = bytearray(4)
    fcntl.ioctl(fd, request, buf, True)
    return struct.unpack("I", buf)[0]


def set_u32(fd: int, request: int, value: int) -> None:
    fcntl.ioctl(fd, request, struct.pack("I", value))


def open_spi(path: str) -> int:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"missing {path}; enable the spi0 overlay and reboot before SPI0 access"
        )
    return os.open(path, os.O_RDWR)


def configure(fd: int, mode: int, speed: int, bits: int) -> None:
    if not 0 <= mode <= 3:
        raise ValueError("SPI mode must be 0..3")
    if speed <= 0:
        raise ValueError("SPI speed must be a positive integer")
    if not 1 <= bits <= 32:
        raise ValueError("bits per word must be 1..32")

    set_u8(fd, SPI_IOC_WR_MODE, mode)
    set_u8(fd, SPI_IOC_WR_BITS_PER_WORD, bits)
    set_u32(fd, SPI_IOC_WR_MAX_SPEED_HZ, speed)


def transfer(fd: int, data: list[int], speed: int, bits: int, delay: int) -> list[int]:
    tx = bytearray(data)
    rx = bytearray(len(tx))
    tx_buf = (ctypes.c_ubyte * len(tx)).from_buffer(tx)
    rx_buf = (ctypes.c_ubyte * len(rx)).from_buffer(rx)
    tx_addr = ctypes.addressof(tx_buf)
    rx_addr = ctypes.addressof(rx_buf)
    message = struct.pack(
        TRANSFER_STRUCT,
        tx_addr,
        rx_addr,
        len(tx),
        speed,
        delay,
        bits,
        0,
        0,
        0,
        0,
        0,
    )
    fcntl.ioctl(fd, SPI_IOC_MESSAGE_1, message)
    return list(rx)


def cmd_status(args: argparse.Namespace) -> int:
    print(f"device={args.device}")
    try:
        fd = open_spi(args.device)
    except OSError as exc:
        print(f"spi_ready=no")
        print(f"error={exc}", file=sys.stderr)
        return 1

    try:
        print("spi_ready=yes")
        print(f"mode={get_u8(fd, SPI_IOC_RD_MODE)}")
        print(f"bits_per_word={get_u8(fd, SPI_IOC_RD_BITS_PER_WORD)}")
        print(f"max_speed_hz={get_u32(fd, SPI_IOC_RD_MAX_SPEED_HZ)}")
    finally:
        os.close(fd)
    return 0


def cmd_transfer(args: argparse.Namespace) -> int:
    if not args.data:
        print("at least one byte is required", file=sys.stderr)
        return 1

    try:
        fd = open_spi(args.device)
    except OSError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 1

    try:
        configure(fd, args.mode, args.speed, args.bits)
        rx = transfer(fd, args.data, args.speed, args.bits, args.delay)
    finally:
        os.close(fd)

    print(f"tx={format_bytes(args.data)}")
    print(f"rx={format_bytes(rx)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="print spidev settings")
    status.add_argument("--device", default=SPI_DEVICE)
    status.set_defaults(func=cmd_status)

    transfer_parser = subparsers.add_parser("transfer", help="write bytes and print received bytes")
    transfer_parser.add_argument("--device", default=SPI_DEVICE)
    transfer_parser.add_argument("--mode", type=int, default=0, help="SPI mode 0..3")
    transfer_parser.add_argument("--speed", type=int, default=500000, help="SPI clock in Hz")
    transfer_parser.add_argument("--bits", type=int, default=8, help="bits per word")
    transfer_parser.add_argument("--delay", type=int, default=0, help="delay usec")
    transfer_parser.add_argument("--data", type=parse_byte, nargs="+", required=True)
    transfer_parser.set_defaults(func=cmd_transfer)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except OSError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
