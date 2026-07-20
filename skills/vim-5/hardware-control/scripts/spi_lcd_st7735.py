#!/usr/bin/env python3
"""Control the VIM 5 expansion-board ST7735 SPI LCD/OLED."""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


WIDTH = 160
HEIGHT = 80
X_OFFSET = 1
Y_OFFSET = 0x1A

DEFAULT_SPI_DEVICE = "/dev/spidev1.0"
DEFAULT_RESET_LINE = "GPIOD_5"
DEFAULT_DC_LINE = "GPIOM_1"
DEFAULT_SPEED_HZ = 8_000_000
SPI_LCD_OVERLAY = "spi1-lcd"
OVERLAY_CONFIG = "/boot/dtb/amlogic/kvim-5.dtb.overlay.env"
OVERLAY_DIR = "/boot/dtb/amlogic/kvim-5.dtb.overlays"

BLACK = 0x0000
WHITE = 0xFFFF
RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F
YELLOW = 0xFFE0
CYAN = 0x07FF

COLORS = {
    "black": BLACK,
    "white": WHITE,
    "red": RED,
    "green": GREEN,
    "blue": BLUE,
    "yellow": YELLOW,
    "cyan": CYAN,
}

GPIO_BANK_TO_CHIP = {
    "GPIOZ": "gpiochip0",
    "GPIOX": "gpiochip1",
    "GPIOD": "gpiochip10",
    "TEST_N": "gpiochip11",
    "GPIOH": "gpiochip2",
    "GPIOM": "gpiochip3",
    "GPIOB": "gpiochip4",
    "GPIOA": "gpiochip5",
    "GPIOY": "gpiochip6",
    "GPIOCC": "gpiochip7",
    "GPIOAO": "gpiochip8",
    "GPIOC": "gpiochip9",
}

FONT_5X7 = {
    " ": (0x00, 0x00, 0x00, 0x00, 0x00),
    ".": (0x00, 0x60, 0x60, 0x00, 0x00),
    "/": (0x20, 0x10, 0x08, 0x04, 0x02),
    "-": (0x08, 0x08, 0x08, 0x08, 0x08),
    "_": (0x40, 0x40, 0x40, 0x40, 0x40),
    ":": (0x00, 0x36, 0x36, 0x00, 0x00),
    "0": (0x3E, 0x51, 0x49, 0x45, 0x3E),
    "1": (0x00, 0x42, 0x7F, 0x40, 0x00),
    "2": (0x42, 0x61, 0x51, 0x49, 0x46),
    "3": (0x21, 0x41, 0x45, 0x4B, 0x31),
    "4": (0x18, 0x14, 0x12, 0x7F, 0x10),
    "5": (0x27, 0x45, 0x45, 0x45, 0x39),
    "6": (0x3C, 0x4A, 0x49, 0x49, 0x30),
    "7": (0x01, 0x71, 0x09, 0x05, 0x03),
    "8": (0x36, 0x49, 0x49, 0x49, 0x36),
    "9": (0x06, 0x49, 0x49, 0x29, 0x1E),
    "A": (0x7E, 0x11, 0x11, 0x11, 0x7E),
    "B": (0x7F, 0x49, 0x49, 0x49, 0x36),
    "C": (0x3E, 0x41, 0x41, 0x41, 0x22),
    "D": (0x7F, 0x41, 0x41, 0x22, 0x1C),
    "E": (0x7F, 0x49, 0x49, 0x49, 0x41),
    "F": (0x7F, 0x09, 0x09, 0x09, 0x01),
    "G": (0x3E, 0x41, 0x49, 0x49, 0x7A),
    "H": (0x7F, 0x08, 0x08, 0x08, 0x7F),
    "I": (0x00, 0x41, 0x7F, 0x41, 0x00),
    "J": (0x20, 0x40, 0x41, 0x3F, 0x01),
    "K": (0x7F, 0x08, 0x14, 0x22, 0x41),
    "L": (0x7F, 0x40, 0x40, 0x40, 0x40),
    "M": (0x7F, 0x02, 0x0C, 0x02, 0x7F),
    "N": (0x7F, 0x04, 0x08, 0x10, 0x7F),
    "O": (0x3E, 0x41, 0x41, 0x41, 0x3E),
    "P": (0x7F, 0x09, 0x09, 0x09, 0x06),
    "Q": (0x3E, 0x41, 0x51, 0x21, 0x5E),
    "R": (0x7F, 0x09, 0x19, 0x29, 0x46),
    "S": (0x46, 0x49, 0x49, 0x49, 0x31),
    "T": (0x01, 0x01, 0x7F, 0x01, 0x01),
    "U": (0x3F, 0x40, 0x40, 0x40, 0x3F),
    "V": (0x1F, 0x20, 0x40, 0x20, 0x1F),
    "W": (0x3F, 0x40, 0x38, 0x40, 0x3F),
    "X": (0x63, 0x14, 0x08, 0x14, 0x63),
    "Y": (0x07, 0x08, 0x70, 0x08, 0x07),
    "Z": (0x61, 0x51, 0x49, 0x45, 0x43),
    "a": (0x20, 0x54, 0x54, 0x54, 0x78),
    "b": (0x7F, 0x48, 0x44, 0x44, 0x38),
    "c": (0x38, 0x44, 0x44, 0x44, 0x20),
    "d": (0x38, 0x44, 0x44, 0x48, 0x7F),
    "e": (0x38, 0x54, 0x54, 0x54, 0x18),
    "f": (0x08, 0x7E, 0x09, 0x01, 0x02),
    "g": (0x0C, 0x52, 0x52, 0x52, 0x3E),
    "h": (0x7F, 0x08, 0x04, 0x04, 0x78),
    "i": (0x00, 0x44, 0x7D, 0x40, 0x00),
    "j": (0x20, 0x40, 0x44, 0x3D, 0x00),
    "k": (0x7F, 0x10, 0x28, 0x44, 0x00),
    "l": (0x00, 0x41, 0x7F, 0x40, 0x00),
    "m": (0x7C, 0x04, 0x18, 0x04, 0x78),
    "n": (0x7C, 0x08, 0x04, 0x04, 0x78),
    "o": (0x38, 0x44, 0x44, 0x44, 0x38),
    "p": (0x7C, 0x14, 0x14, 0x14, 0x08),
    "q": (0x08, 0x14, 0x14, 0x18, 0x7C),
    "r": (0x7C, 0x08, 0x04, 0x04, 0x08),
    "s": (0x48, 0x54, 0x54, 0x54, 0x20),
    "t": (0x04, 0x3F, 0x44, 0x40, 0x20),
    "u": (0x3C, 0x40, 0x40, 0x20, 0x7C),
    "v": (0x1C, 0x20, 0x40, 0x20, 0x1C),
    "w": (0x3C, 0x40, 0x30, 0x40, 0x3C),
    "x": (0x44, 0x28, 0x10, 0x28, 0x44),
    "y": (0x0C, 0x50, 0x50, 0x50, 0x3C),
    "z": (0x44, 0x64, 0x54, 0x4C, 0x44),
}


class GpioError(RuntimeError):
    pass


def parse_spidev(path: str) -> tuple[int, int]:
    base = os.path.basename(path)
    if not base.startswith("spidev") or "." not in base:
        raise ValueError(f"bad spidev path: {path}")
    bus, dev = base.removeprefix("spidev").split(".", 1)
    return int(bus), int(dev)


def resolve_gpio_line(name: str) -> tuple[str, int]:
    match = re.fullmatch(r"([A-Za-z0-9_]+)_(\d+)", name)
    if match:
        bank, offset = match.group(1).upper(), int(match.group(2))
        chip = GPIO_BANK_TO_CHIP.get(bank)
        if chip is not None:
            return chip, offset

    match = re.fullmatch(r"(?:/dev/)?(gpiochip\d+)[_:](\d+)", name)
    if match:
        return match.group(1), int(match.group(2))

    try:
        out = subprocess.check_output(["gpiofind", name], text=True).strip()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        raise GpioError(f"cannot resolve GPIO line {name!r}; use e.g. GPIOD_5 or gpiochip10:5") from exc

    parts = out.split()
    if len(parts) != 2:
        raise GpioError(f"unexpected gpiofind output for {name!r}: {out!r}")
    return parts[0], int(parts[1])


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def command_available(name: str) -> bool:
    return shutil.which(name) is not None


class PythonGpiodPin:
    def __init__(self, line_name: str, initial: int = 0) -> None:
        self.line_name = line_name
        self.chip_name, self.offset = resolve_gpio_line(line_name)
        self._chip = None
        self._line = None
        self._request = None
        self._version = None

        import gpiod

        if hasattr(gpiod, "request_lines"):
            from gpiod.line import Direction, Value

            settings = gpiod.LineSettings(
                direction=Direction.OUTPUT,
                output_value=Value.ACTIVE if initial else Value.INACTIVE,
            )
            self._value_enum = Value
            self._request = gpiod.request_lines(
                f"/dev/{self.chip_name}",
                consumer="vim-5-spi-lcd-st7735",
                config={self.offset: settings},
            )
            self._version = 2
        else:
            self._chip = gpiod.Chip(self.chip_name)
            self._line = self._chip.get_line(self.offset)
            self._line.request(
                consumer="vim-5-spi-lcd-st7735",
                type=gpiod.LINE_REQ_DIR_OUT,
                default_vals=[1 if initial else 0],
            )
            self._version = 1

    def set(self, value: int) -> None:
        value = 1 if value else 0
        if self._version == 2:
            enum_value = self._value_enum.ACTIVE if value else self._value_enum.INACTIVE
            self._request.set_value(self.offset, enum_value)
        else:
            self._line.set_value(value)

    def close(self) -> None:
        if self._request is not None:
            self._request.release()
        if self._line is not None:
            self._line.release()
        if self._chip is not None:
            self._chip.close()


class GpioSetPin:
    def __init__(self, line_name: str, initial: int = 0) -> None:
        self.line_name = line_name
        self.chip_name, self.offset = resolve_gpio_line(line_name)
        self._proc = None
        self._syntax = None
        self.set(initial)

    def _start(self, value: int):
        value_arg = f"{self.offset}={1 if value else 0}"
        candidates = []
        if self._syntax in (None, "v1-long"):
            candidates.append(("v1-long", ["gpioset", "--mode=signal", self.chip_name, value_arg]))
        if self._syntax in (None, "v1-short"):
            candidates.append(("v1-short", ["gpioset", "-m", "signal", self.chip_name, value_arg]))
        if self._syntax in (None, "v2"):
            candidates.append(("v2", ["gpioset", "-c", self.chip_name, value_arg]))

        last_error = None
        for syntax, cmd in candidates:
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except FileNotFoundError as exc:
                raise GpioError("gpioset not found; install package gpiod") from exc

            time.sleep(0.03)
            if proc.poll() is None:
                self._syntax = syntax
                return proc

            if syntax == "v2" and proc.returncode == 0:
                self._syntax = syntax
                return None

            last_error = proc.returncode

        raise GpioError(f"gpioset failed for {self.line_name}; last exit code: {last_error}")

    def set(self, value: int) -> None:
        old = self._proc
        if old is not None and old.poll() is None:
            old.terminate()
            try:
                old.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                old.kill()
                old.wait(timeout=0.2)
        self._proc = self._start(value)

    def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                self._proc.kill()


def make_pin(line_name: str, initial: int, mode: str):
    if mode in ("auto", "gpiod"):
        try:
            return PythonGpiodPin(line_name, initial)
        except Exception:
            if mode == "gpiod":
                raise
    return GpioSetPin(line_name, initial)


class LcdSt7735:
    def __init__(
        self,
        spi_path: str,
        reset_line: str,
        dc_line: str,
        gpio_mode: str,
        speed_hz: int,
    ) -> None:
        try:
            import spidev
        except ImportError as exc:
            raise RuntimeError("missing python spidev module; install package python3-spidev") from exc

        bus, dev = parse_spidev(spi_path)
        self.spi = spidev.SpiDev()
        self.spi.open(bus, dev)
        self.spi.mode = 0
        self.spi.max_speed_hz = speed_hz
        self.spi.bits_per_word = 8
        self.spi.no_cs = False
        self.reset = make_pin(reset_line, 1, gpio_mode)
        self.dc = make_pin(dc_line, 0, gpio_mode)

    def close(self) -> None:
        self.spi.close()
        self.dc.close()
        self.reset.close()

    def hard_reset(self) -> None:
        self.reset.set(0)
        time.sleep(0.1)
        self.reset.set(1)
        time.sleep(0.1)

    def write_cmd(self, cmd: int, data=()) -> None:
        self.dc.set(0)
        self.spi.writebytes([cmd & 0xFF])
        if data:
            self.dc.set(1)
            self.write_data(data)

    def write_data(self, data) -> None:
        self.dc.set(1)
        data = bytes(data)
        for start in range(0, len(data), 4096):
            self.spi.writebytes2(data[start : start + 4096])

    def init(self) -> None:
        self.hard_reset()
        self.write_cmd(0x11)
        time.sleep(0.12)
        self.write_cmd(0x21)
        self.write_cmd(0xB1, [0x05, 0x3A, 0x3A])
        self.write_cmd(0xB2, [0x05, 0x3A, 0x3A])
        self.write_cmd(0xB3, [0x05, 0x3A, 0x3A, 0x05, 0x3A, 0x3A])
        self.write_cmd(0xB4, [0x03])
        self.write_cmd(0xC0, [0x62, 0x02, 0x04])
        self.write_cmd(0xC1, [0xC0])
        self.write_cmd(0xC2, [0x0D, 0x00])
        self.write_cmd(0xC3, [0x8D, 0x6A])
        self.write_cmd(0xC4, [0x8D, 0xEE])
        self.write_cmd(0xC5, [0x0E])
        self.write_cmd(
            0xE0,
            [
                0x10,
                0x0E,
                0x02,
                0x03,
                0x0E,
                0x07,
                0x02,
                0x07,
                0x0A,
                0x12,
                0x27,
                0x37,
                0x00,
                0x0D,
                0x0E,
                0x10,
            ],
        )
        self.write_cmd(
            0xE1,
            [
                0x10,
                0x0E,
                0x03,
                0x03,
                0x0F,
                0x06,
                0x02,
                0x08,
                0x0A,
                0x13,
                0x26,
                0x36,
                0x00,
                0x0D,
                0x0E,
                0x10,
            ],
        )
        self.write_cmd(0x3A, [0x05])
        self.write_cmd(0x36, [0x68])
        self.write_cmd(0x29)
        time.sleep(0.05)

    def set_window(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self.write_cmd(0x2A, [0x00, x0 + X_OFFSET, 0x00, x1 + X_OFFSET])
        self.write_cmd(0x2B, [0x00, y0 + Y_OFFSET, 0x00, y1 + Y_OFFSET])
        self.write_cmd(0x2C)

    def flush(self, pixels: list[int]) -> None:
        self.set_window(0, 0, WIDTH - 1, HEIGHT - 1)
        out = bytearray(WIDTH * HEIGHT * 2)
        pos = 0
        for color in pixels:
            out[pos] = (color >> 8) & 0xFF
            out[pos + 1] = color & 0xFF
            pos += 2
        self.write_data(out)


def fill(pixels: list[int], color: int) -> None:
    pixels[:] = [color] * (WIDTH * HEIGHT)


def draw_rect(pixels: list[int], x: int, y: int, w: int, h: int, color: int) -> None:
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(WIDTH, x + w)
    y1 = min(HEIGHT, y + h)
    for yy in range(y0, y1):
        row = yy * WIDTH
        for xx in range(x0, x1):
            pixels[row + xx] = color


def draw_char(pixels: list[int], x: int, y: int, ch: str, color: int, scale: int = 1) -> None:
    glyph = FONT_5X7.get(ch, FONT_5X7.get(ch.upper(), FONT_5X7[" "]))
    for col, bits in enumerate(glyph):
        for row in range(7):
            if bits & (1 << row):
                draw_rect(pixels, x + col * scale, y + row * scale, scale, scale, color)


def draw_text(pixels: list[int], x: int, y: int, text: str, color: int, scale: int = 1) -> None:
    cursor = x
    for ch in text:
        draw_char(pixels, cursor, y, ch, color, scale)
        cursor += 6 * scale


def build_test_frame() -> list[int]:
    pixels = [BLACK] * (WIDTH * HEIGHT)
    draw_text(pixels, 26, 18, "Khadas", WHITE, 3)
    draw_text(pixels, 35, 48, "VIM 5", BLUE, 3)
    return pixels


def build_text_frame(lines: list[str], color: int, background: int, scale: int) -> list[int]:
    pixels = [background] * (WIDTH * HEIGHT)
    y = 8
    for line in lines[:4]:
        draw_text(pixels, 8, y, line, color, scale)
        y += 10 * scale
    return pixels


def open_lcd(args: argparse.Namespace) -> LcdSt7735:
    return LcdSt7735(args.spi, args.reset_line, args.dc_line, args.gpio_mode, args.speed_hz)


def command_state(command: str) -> str:
    path = shutil.which(command)
    return f"present:{path}" if path else "missing"


def module_state(module: str) -> str:
    return "present" if module_available(module) else "missing"


def gpio_line_status(label: str, value: str) -> str:
    try:
        chip, offset = resolve_gpio_line(value)
    except GpioError as exc:
        return f"{label}_line={value} unresolved:{exc}"
    return f"{label}_line={value} resolved=/dev/{chip}:{offset}"


def cmd_status(args: argparse.Namespace) -> int:
    spi_path = Path(args.spi)
    spidev_ok = module_available("spidev")
    gpiod_ok = module_available("gpiod")
    gpioset_ok = command_available("gpioset")
    ready = spi_path.exists() and spidev_ok and (gpiod_ok or gpioset_ok)

    print("display=ST7735_160x80")
    print(f"required_overlay={SPI_LCD_OVERLAY}")
    print(f"overlay_config={OVERLAY_CONFIG}")
    print(f"overlay_dir={OVERLAY_DIR}")
    print(f"spi_device={args.spi}")
    print(f"spi_device_node={'present' if spi_path.exists() else 'missing'}")
    print(f"default_reset_line={DEFAULT_RESET_LINE}")
    print(f"default_dc_line={DEFAULT_DC_LINE}")
    print(gpio_line_status("reset", args.reset_line))
    print(gpio_line_status("dc", args.dc_line))
    print("apt_dependencies=python3-spidev gpiod python3-libgpiod")
    print("required_python_module_spidev=" + module_state("spidev"))
    print("optional_python_module_gpiod=" + module_state("gpiod"))
    print("command_gpioset=" + command_state("gpioset"))
    print("command_gpiofind=" + command_state("gpiofind"))
    print("note=python3-libgpiod is optional when gpioset from package gpiod is available")
    print("pin_conflict=spi1-lcd uses SPI pins; avoid conflicting ext-board-codec, i2s, or spi overlays")
    print(f"spi_lcd_ready={'yes' if ready else 'no'}")
    if not spi_path.exists():
        print(f"missing_node_note=enable {SPI_LCD_OVERLAY} in fdt_overlays and reboot")
    if not spidev_ok:
        print("missing_dependency_note=install python3-spidev")
    if not (gpiod_ok or gpioset_ok):
        print("missing_gpio_dependency_note=install gpiod or python3-libgpiod")
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    lcd = open_lcd(args)
    try:
        lcd.init()
        lcd.flush(build_test_frame())
    finally:
        lcd.close()
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    lcd = open_lcd(args)
    try:
        lcd.init()
        lcd.flush([COLORS[args.color]] * (WIDTH * HEIGHT))
    finally:
        lcd.close()
    return 0


def cmd_text(args: argparse.Namespace) -> int:
    lcd = open_lcd(args)
    try:
        lcd.init()
        lcd.flush(build_text_frame(args.line, COLORS[args.color], COLORS[args.background], args.scale))
    finally:
        lcd.close()
    return 0


def add_common_lcd_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--spi", default=DEFAULT_SPI_DEVICE)
    parser.add_argument("--reset-line", default=DEFAULT_RESET_LINE)
    parser.add_argument("--dc-line", default=DEFAULT_DC_LINE)
    parser.add_argument("--gpio-mode", choices=("auto", "gpiod", "gpioset"), default="auto")
    parser.add_argument("--speed-hz", type=int, default=DEFAULT_SPEED_HZ)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="print device, overlay, and dependency status")
    add_common_lcd_args(status)
    status.set_defaults(func=cmd_status)

    test = subparsers.add_parser("test", help="draw the default VIM 5 test frame")
    add_common_lcd_args(test)
    test.set_defaults(func=cmd_test)

    clear = subparsers.add_parser("clear", help="clear the display to one color")
    add_common_lcd_args(clear)
    clear.add_argument("--color", choices=sorted(COLORS), default="black")
    clear.set_defaults(func=cmd_clear)

    text = subparsers.add_parser("text", help="draw up to four text lines")
    add_common_lcd_args(text)
    text.add_argument("--line", action="append", required=True, help="line to draw; repeatable")
    text.add_argument("--color", choices=sorted(COLORS), default="white")
    text.add_argument("--background", choices=sorted(COLORS), default="black")
    text.add_argument("--scale", type=int, choices=(1, 2, 3), default=2)
    text.set_defaults(func=cmd_text)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"spi_lcd_st7735.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
