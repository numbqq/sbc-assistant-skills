#!/usr/bin/env python3
"""Minimal SSD1306 I2C OLED demo for Khadas VIM4.

Examples:
  sudo python3 oled_ssd1306_demo.py --bus 5 --addr 0x3c
  sudo python3 oled_ssd1306_demo.py --bus 5 --addr 0x3c --fill
"""

import argparse
import fcntl
import os
import time


I2C_SLAVE = 0x0703
WIDTH = 128
HEIGHT = 64
PAGES = HEIGHT // 8


FONT_5X7 = {
    " ": [0x00, 0x00, 0x00, 0x00, 0x00],
    "!": [0x00, 0x00, 0x5f, 0x00, 0x00],
    ".": [0x00, 0x60, 0x60, 0x00, 0x00],
    "-": [0x08, 0x08, 0x08, 0x08, 0x08],
    "0": [0x3e, 0x51, 0x49, 0x45, 0x3e],
    "1": [0x00, 0x42, 0x7f, 0x40, 0x00],
    "2": [0x42, 0x61, 0x51, 0x49, 0x46],
    "3": [0x21, 0x41, 0x45, 0x4b, 0x31],
    "4": [0x18, 0x14, 0x12, 0x7f, 0x10],
    "5": [0x27, 0x45, 0x45, 0x45, 0x39],
    "6": [0x3c, 0x4a, 0x49, 0x49, 0x30],
    "7": [0x01, 0x71, 0x09, 0x05, 0x03],
    "8": [0x36, 0x49, 0x49, 0x49, 0x36],
    "9": [0x06, 0x49, 0x49, 0x29, 0x1e],
    "A": [0x7e, 0x11, 0x11, 0x11, 0x7e],
    "B": [0x7f, 0x49, 0x49, 0x49, 0x36],
    "C": [0x3e, 0x41, 0x41, 0x41, 0x22],
    "D": [0x7f, 0x41, 0x41, 0x22, 0x1c],
    "E": [0x7f, 0x49, 0x49, 0x49, 0x41],
    "F": [0x7f, 0x09, 0x09, 0x09, 0x01],
    "G": [0x3e, 0x41, 0x49, 0x49, 0x7a],
    "H": [0x7f, 0x08, 0x08, 0x08, 0x7f],
    "I": [0x00, 0x41, 0x7f, 0x41, 0x00],
    "J": [0x20, 0x40, 0x41, 0x3f, 0x01],
    "K": [0x7f, 0x08, 0x14, 0x22, 0x41],
    "L": [0x7f, 0x40, 0x40, 0x40, 0x40],
    "M": [0x7f, 0x02, 0x0c, 0x02, 0x7f],
    "N": [0x7f, 0x04, 0x08, 0x10, 0x7f],
    "O": [0x3e, 0x41, 0x41, 0x41, 0x3e],
    "P": [0x7f, 0x09, 0x09, 0x09, 0x06],
    "Q": [0x3e, 0x41, 0x51, 0x21, 0x5e],
    "R": [0x7f, 0x09, 0x19, 0x29, 0x46],
    "S": [0x46, 0x49, 0x49, 0x49, 0x31],
    "T": [0x01, 0x01, 0x7f, 0x01, 0x01],
    "U": [0x3f, 0x40, 0x40, 0x40, 0x3f],
    "V": [0x1f, 0x20, 0x40, 0x20, 0x1f],
    "W": [0x3f, 0x40, 0x38, 0x40, 0x3f],
    "X": [0x63, 0x14, 0x08, 0x14, 0x63],
    "Y": [0x07, 0x08, 0x70, 0x08, 0x07],
    "Z": [0x61, 0x51, 0x49, 0x45, 0x43],
}


class SSD1306:
    def __init__(self, bus: int, addr: int) -> None:
        self.path = f"/dev/i2c-{bus}"
        self.addr = addr
        self.fd = os.open(self.path, os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE, addr)

    def close(self) -> None:
        os.close(self.fd)

    def write(self, control: int, data: list[int]) -> None:
        packet = bytes([control, *data])
        os.write(self.fd, packet)

    def command(self, *values: int) -> None:
        self.write(0x00, list(values))

    def data(self, values: list[int]) -> None:
        # Keep transfers small enough for common I2C adapters.
        for start in range(0, len(values), 16):
            self.write(0x40, values[start : start + 16])

    def init(self) -> None:
        self.command(0xAE)  # display off
        self.command(0xD5, 0x80)
        self.command(0xA8, HEIGHT - 1)
        self.command(0xD3, 0x00)
        self.command(0x40)
        self.command(0x8D, 0x14)
        self.command(0x20, 0x00)
        self.command(0xA1)
        self.command(0xC8)
        self.command(0xDA, 0x12)
        self.command(0x81, 0xCF)
        self.command(0xD9, 0xF1)
        self.command(0xDB, 0x40)
        self.command(0xA4)
        self.command(0xA6)
        self.command(0x2E)
        self.command(0xAF)  # display on

    def set_page(self, page: int, col: int = 0) -> None:
        self.command(0xB0 | page)
        self.command(0x00 | (col & 0x0F))
        self.command(0x10 | ((col >> 4) & 0x0F))

    def clear(self) -> None:
        for page in range(PAGES):
            self.set_page(page)
            self.data([0x00] * WIDTH)

    def fill(self, value: int) -> None:
        for page in range(PAGES):
            self.set_page(page)
            self.data([value & 0xFF] * WIDTH)

    def draw_page_text(self, page: int, col: int, text: str) -> None:
        self.set_page(page, col)
        line: list[int] = []
        for ch in text.upper():
            line.extend(FONT_5X7.get(ch, FONT_5X7[" "]))
            line.append(0x00)
        self.data(line[: max(0, WIDTH - col)])

    def draw_demo(self) -> None:
        self.clear()
        self.draw_page_text(0, 0, "VIM4 OLED")
        self.draw_page_text(2, 0, "I2C-5 0X3C")
        self.draw_page_text(4, 0, "SSD1306 OK")
        for page in range(6, PAGES):
            self.set_page(page)
            self.data([0xAA if x % 2 else 0x55 for x in range(WIDTH)])


def parse_int(value: str) -> int:
    return int(value, 0)


def main() -> int:
    parser = argparse.ArgumentParser(description="light a 128x64 SSD1306 OLED over I2C")
    parser.add_argument("--bus", type=parse_int, default=5)
    parser.add_argument("--addr", type=parse_int, default=0x3C)
    parser.add_argument("--fill", action="store_true", help="fill the whole display")
    parser.add_argument("--seconds", type=float, default=0.0, help="sleep before exit")
    args = parser.parse_args()

    oled = SSD1306(args.bus, args.addr)
    try:
        oled.init()
        if args.fill:
            oled.fill(0xFF)
        else:
            oled.draw_demo()
        if args.seconds > 0:
            time.sleep(args.seconds)
    finally:
        oled.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
