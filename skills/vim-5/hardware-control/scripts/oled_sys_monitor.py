#!/usr/bin/env python3
"""Show VIM 5 CPU, memory, and time on a 128x64 SSD1306 I2C OLED.

Default target:
  - I2C bus: /dev/i2c-3
  - OLED address: 0x3c

Examples:
  sudo python3 oled_sys_monitor.py
  sudo python3 oled_sys_monitor.py --bus 3 --addr 0x3c --interval 1
"""

from __future__ import annotations

import argparse
import fcntl
import os
import signal
import time


I2C_SLAVE = 0x0703
WIDTH = 128
HEIGHT = 64
PAGES = HEIGHT // 8


FONT_5X7 = {
    " ": [0x00, 0x00, 0x00, 0x00, 0x00],
    "!": [0x00, 0x00, 0x5F, 0x00, 0x00],
    "%": [0x23, 0x13, 0x08, 0x64, 0x62],
    ".": [0x00, 0x60, 0x60, 0x00, 0x00],
    "/": [0x20, 0x10, 0x08, 0x04, 0x02],
    ":": [0x00, 0x36, 0x36, 0x00, 0x00],
    "-": [0x08, 0x08, 0x08, 0x08, 0x08],
    "0": [0x3E, 0x51, 0x49, 0x45, 0x3E],
    "1": [0x00, 0x42, 0x7F, 0x40, 0x00],
    "2": [0x42, 0x61, 0x51, 0x49, 0x46],
    "3": [0x21, 0x41, 0x45, 0x4B, 0x31],
    "4": [0x18, 0x14, 0x12, 0x7F, 0x10],
    "5": [0x27, 0x45, 0x45, 0x45, 0x39],
    "6": [0x3C, 0x4A, 0x49, 0x49, 0x30],
    "7": [0x01, 0x71, 0x09, 0x05, 0x03],
    "8": [0x36, 0x49, 0x49, 0x49, 0x36],
    "9": [0x06, 0x49, 0x49, 0x29, 0x1E],
    "A": [0x7E, 0x11, 0x11, 0x11, 0x7E],
    "B": [0x7F, 0x49, 0x49, 0x49, 0x36],
    "C": [0x3E, 0x41, 0x41, 0x41, 0x22],
    "D": [0x7F, 0x41, 0x41, 0x22, 0x1C],
    "E": [0x7F, 0x49, 0x49, 0x49, 0x41],
    "F": [0x7F, 0x09, 0x09, 0x09, 0x01],
    "G": [0x3E, 0x41, 0x49, 0x49, 0x7A],
    "H": [0x7F, 0x08, 0x08, 0x08, 0x7F],
    "I": [0x00, 0x41, 0x7F, 0x41, 0x00],
    "J": [0x20, 0x40, 0x41, 0x3F, 0x01],
    "K": [0x7F, 0x08, 0x14, 0x22, 0x41],
    "L": [0x7F, 0x40, 0x40, 0x40, 0x40],
    "M": [0x7F, 0x02, 0x0C, 0x02, 0x7F],
    "N": [0x7F, 0x04, 0x08, 0x10, 0x7F],
    "O": [0x3E, 0x41, 0x41, 0x41, 0x3E],
    "P": [0x7F, 0x09, 0x09, 0x09, 0x06],
    "Q": [0x3E, 0x41, 0x51, 0x21, 0x5E],
    "R": [0x7F, 0x09, 0x19, 0x29, 0x46],
    "S": [0x46, 0x49, 0x49, 0x49, 0x31],
    "T": [0x01, 0x01, 0x7F, 0x01, 0x01],
    "U": [0x3F, 0x40, 0x40, 0x40, 0x3F],
    "V": [0x1F, 0x20, 0x40, 0x20, 0x1F],
    "W": [0x3F, 0x40, 0x38, 0x40, 0x3F],
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
        os.write(self.fd, bytes([control, *data]))

    def command(self, *values: int) -> None:
        self.write(0x00, list(values))

    def data(self, values: list[int]) -> None:
        for start in range(0, len(values), 16):
            self.write(0x40, values[start : start + 16])

    def init(self) -> None:
        self.command(0xAE)
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
        self.command(0xAF)

    def set_page(self, page: int, col: int = 0) -> None:
        self.command(0xB0 | page)
        self.command(0x00 | (col & 0x0F))
        self.command(0x10 | ((col >> 4) & 0x0F))

    def clear_page(self, page: int) -> None:
        self.set_page(page)
        self.data([0x00] * WIDTH)

    def clear(self) -> None:
        for page in range(PAGES):
            self.clear_page(page)

    def draw_page_text(self, page: int, col: int, text: str) -> None:
        line: list[int] = []
        for ch in text.upper():
            line.extend(FONT_5X7.get(ch, FONT_5X7[" "]))
            line.append(0x00)

        available = max(0, WIDTH - col)
        self.set_page(page, col)
        self.data(line[:available] + [0x00] * max(0, available - len(line)))

    def draw_bar(self, page: int, percent: float) -> None:
        filled = round((WIDTH - 2) * max(0.0, min(100.0, percent)) / 100.0)
        bar = [0x7E]
        for col in range(WIDTH - 2):
            bar.append(0x7E if col < filled else 0x42)
        bar.append(0x7E)
        self.set_page(page)
        self.data(bar)


def parse_int(value: str) -> int:
    return int(value, 0)


def read_cpu_ticks() -> tuple[int, int]:
    with open("/proc/stat", "r", encoding="ascii") as stat:
        fields = stat.readline().split()

    values = [int(value) for value in fields[1:]]
    idle = values[3] + values[4]
    total = sum(values)
    return idle, total


def cpu_percent(previous: tuple[int, int], current: tuple[int, int]) -> float:
    prev_idle, prev_total = previous
    idle, total = current
    total_delta = total - prev_total
    idle_delta = idle - prev_idle
    if total_delta <= 0:
        return 0.0
    return 100.0 * (total_delta - idle_delta) / total_delta


def read_memory_gib() -> tuple[float, float, float]:
    info: dict[str, int] = {}
    with open("/proc/meminfo", "r", encoding="ascii") as meminfo:
        for line in meminfo:
            key, raw_value = line.split(":", 1)
            info[key] = int(raw_value.strip().split()[0])

    total = info["MemTotal"]
    available = info.get("MemAvailable", info.get("MemFree", 0))
    used = total - available
    used_percent = 100.0 * used / total if total else 0.0
    return used / 1048576.0, total / 1048576.0, used_percent


def render_status(oled: SSD1306, cpu: float, mem_used: float, mem_total: float, mem_percent: float) -> None:
    now = time.strftime("%H:%M:%S")
    date = time.strftime("%Y-%m-%d")

    oled.draw_page_text(0, 0, f"CPU {cpu:5.1f}%")
    oled.draw_bar(1, cpu)
    oled.draw_page_text(3, 0, f"MEM {mem_used:4.1f}/{mem_total:4.1f}G")
    oled.draw_page_text(4, 0, f"USED {mem_percent:5.1f}%")
    oled.draw_page_text(6, 0, f"TIME {now}")
    oled.draw_page_text(7, 0, date)


def main() -> int:
    parser = argparse.ArgumentParser(description="display CPU, memory, and time on SSD1306 OLED")
    parser.add_argument("--bus", type=parse_int, default=3, help="I2C bus number, default: 3")
    parser.add_argument("--addr", type=parse_int, default=0x3C, help="OLED I2C address, default: 0x3c")
    parser.add_argument("--interval", type=float, default=1.0, help="refresh interval in seconds")
    args = parser.parse_args()

    stop = False

    def handle_signal(signum: int, frame: object) -> None:
        del signum, frame
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    oled = SSD1306(args.bus, args.addr)
    try:
        oled.init()
        oled.clear()
        previous_cpu = read_cpu_ticks()
        while not stop:
            time.sleep(args.interval)
            current_cpu = read_cpu_ticks()
            cpu = cpu_percent(previous_cpu, current_cpu)
            previous_cpu = current_cpu
            mem_used, mem_total, mem_percent = read_memory_gib()
            render_status(oled, cpu, mem_used, mem_total, mem_percent)
    finally:
        oled.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
