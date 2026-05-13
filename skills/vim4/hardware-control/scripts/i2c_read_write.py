#!/usr/bin/env python3
"""Minimal VIM4 I2C helper using Linux /dev/i2c-*.

Examples:
  sudo python3 i2c_read_write.py read --bus 5 --addr 0x40 --reg 0x00
  sudo python3 i2c_read_write.py write --bus 5 --addr 0x40 --reg 0x01 --value 0xff
  sudo python3 i2c_read_write.py write-bytes --bus 5 --addr 0x3c --data 0x00 0xae
  sudo python3 i2c_read_write.py read-raw --bus 5 --addr 0x40 --length 4
"""

import argparse
import fcntl
import os


I2C_SLAVE = 0x0703


class I2CDevice:
    def __init__(self, bus: int, addr: int) -> None:
        self.path = f"/dev/i2c-{bus}"
        self.addr = addr
        self.fd = -1

    def __enter__(self) -> "I2CDevice":
        self.fd = os.open(self.path, os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE, self.addr)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        os.close(self.fd)

    def write(self, data: list[int]) -> None:
        os.write(self.fd, bytes(data))

    def read(self, length: int) -> bytes:
        return os.read(self.fd, length)

    def read_register(self, reg: int, length: int) -> bytes:
        self.write([reg])
        return self.read(length)

    def write_register(self, reg: int, value: int) -> None:
        self.write([reg, value])


def parse_int(text: str) -> int:
    return int(text, 0)


def byte_value(value: int, name: str) -> int:
    if not 0 <= value <= 0xFF:
        raise argparse.ArgumentTypeError(f"{name} must be 0..255")
    return value


def parse_byte(text: str) -> int:
    return byte_value(parse_int(text), text)


def print_bytes(data: bytes) -> None:
    print(" ".join(f"0x{value:02x}" for value in data))


def main() -> int:
    parser = argparse.ArgumentParser(description="minimal /dev/i2c-* read/write helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    read = sub.add_parser("read")
    read.add_argument("--bus", type=parse_int, required=True)
    read.add_argument("--addr", type=parse_int, required=True)
    read.add_argument("--reg", type=parse_byte, required=True)
    read.add_argument("--length", type=parse_int, default=1)

    write = sub.add_parser("write")
    write.add_argument("--bus", type=parse_int, required=True)
    write.add_argument("--addr", type=parse_int, required=True)
    write.add_argument("--reg", type=parse_byte, required=True)
    write.add_argument("--value", type=parse_byte, required=True)

    write_bytes = sub.add_parser("write-bytes")
    write_bytes.add_argument("--bus", type=parse_int, required=True)
    write_bytes.add_argument("--addr", type=parse_int, required=True)
    write_bytes.add_argument("--data", type=parse_byte, nargs="+", required=True)

    read_raw = sub.add_parser("read-raw")
    read_raw.add_argument("--bus", type=parse_int, required=True)
    read_raw.add_argument("--addr", type=parse_int, required=True)
    read_raw.add_argument("--length", type=parse_int, required=True)

    args = parser.parse_args()
    if hasattr(args, "length") and args.length <= 0:
        parser.error("--length must be greater than 0")

    with I2CDevice(args.bus, args.addr) as dev:
        if args.cmd == "read":
            print_bytes(dev.read_register(args.reg, args.length))
        elif args.cmd == "write":
            dev.write_register(args.reg, args.value)
            print("ok")
        elif args.cmd == "write-bytes":
            dev.write(args.data)
            print("ok")
        elif args.cmd == "read-raw":
            print_bytes(dev.read(args.length))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
