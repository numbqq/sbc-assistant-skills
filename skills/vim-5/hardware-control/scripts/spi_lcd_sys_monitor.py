#!/usr/bin/env python3
"""Show VIM 5 CPU, memory, and CPU temperature on the SPI LCD.

The script reuses the bundled ST7735 helper from the VIM 5 skill when it is
available locally or from the installed skill bundle.

Examples:
  python3 scripts/spi_lcd_sys_monitor.py --interval 1
  python3 scripts/spi_lcd_sys_monitor.py --status
  /usr/bin/python3 scripts/spi_lcd_sys_monitor.py --interval 1
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path


HELPER_CANDIDATES = [
    Path(__file__).with_name("spi_lcd_st7735.py"),
    Path("/home/khadas/.codex/skills/khadas-vim-5-hardware-control/scripts/spi_lcd_st7735.py"),
]

_HELPER_MODULE = None
_HELPER_PATH: Path | None = None

WIDTH = 160
HEIGHT = 80

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
YELLOW = 0xFFE0
CYAN = 0x07FF


def get_helper():
    global _HELPER_MODULE, _HELPER_PATH
    if _HELPER_MODULE is not None:
        return _HELPER_MODULE
    for helper_path in HELPER_CANDIDATES:
        if not helper_path.exists():
            continue
        spec = importlib.util.spec_from_file_location("vim5_spi_lcd_st7735", helper_path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        _HELPER_MODULE = module
        _HELPER_PATH = helper_path
        return module
    raise RuntimeError("spi_lcd_st7735.py not found; expected a local copy or the VIM 5 skill helper")


def helper_path_label() -> str:
    if _HELPER_PATH is not None:
        return str(_HELPER_PATH)
    for helper_path in HELPER_CANDIDATES:
        if helper_path.exists():
            return f"present:{helper_path}"
    return "missing"


THERMAL_ROOT = Path("/sys/class/thermal")
FAN_SCRIPT = Path("/usr/local/bin/fan.sh")


def read_cpu_ticks() -> tuple[int, int]:
    fields = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0].split()
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
    return max(0.0, min(100.0, 100.0 * (total_delta - idle_delta) / total_delta))


def read_memory_stats() -> tuple[float, float, float]:
    info: dict[str, int] = {}
    with Path("/proc/meminfo").open("r", encoding="ascii") as meminfo:
        for line in meminfo:
            key, raw_value = line.split(":", 1)
            info[key] = int(raw_value.strip().split()[0])

    total_mib = float(info["MemTotal"])
    available_mib = float(info.get("MemAvailable", info.get("MemFree", 0)))
    used_mib = max(0.0, total_mib - available_mib)
    used_percent = 100.0 * used_mib / total_mib if total_mib else 0.0
    return used_mib, total_mib, used_percent


def format_gib_value(mib: float) -> str:
    gib = mib / 1024.0
    return f"{gib:0.1f}"


def thermal_candidates() -> list[tuple[int, Path, int]]:
    candidates: list[tuple[int, Path, int]] = []
    for zone in sorted(THERMAL_ROOT.glob("thermal_zone*")):
        temp_path = zone / "temp"
        if not temp_path.is_file():
            continue
        try:
            raw_temp = int(temp_path.read_text(encoding="ascii").strip())
        except (OSError, ValueError):
            continue

        zone_type = ""
        type_path = zone / "type"
        if type_path.is_file():
            try:
                zone_type = type_path.read_text(encoding="ascii").strip().lower()
            except OSError:
                zone_type = ""

        score = 0
        if "cpu" in zone_type:
            score += 100
        if "soc" in zone_type:
            score += 80
        if "package" in zone_type:
            score += 70
        if "thermal" in zone_type:
            score += 10
        candidates.append((score, zone, raw_temp))
    return candidates


def probe_cpu_temperature() -> tuple[str | None, float | None]:
    candidates = thermal_candidates()
    if candidates:
        score, zone, raw_temp = sorted(candidates, key=lambda item: item[0], reverse=True)[0]
        del score
        return str(zone / "temp"), raw_temp / 1000.0

    if FAN_SCRIPT.is_file() and os.access(FAN_SCRIPT, os.X_OK):
        try:
            output = subprocess.check_output(
                [str(FAN_SCRIPT), "temp"], text=True, stderr=subprocess.STDOUT
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None, None
        match = re.search(r"-?\d+(?:\.\d+)?", output)
        if match:
            return f"{FAN_SCRIPT} temp", float(match.group(0))

    return None, None


def read_cpu_temperature() -> float | None:
    _, temp_c = probe_cpu_temperature()
    return temp_c


def cpu_bar_color(cpu: float) -> int:
    if cpu < 60.0:
        return GREEN
    if cpu < 85.0:
        return YELLOW
    return RED


def temp_color(temp_c: float | None) -> int:
    if temp_c is None:
        return WHITE
    if temp_c < 55.0:
        return GREEN
    if temp_c < 75.0:
        return YELLOW
    return RED


def draw_cpu_bar(helper, pixels: list[int], cpu: float) -> None:
    x = 8
    y = 38
    width = 144
    height = 6
    inner_width = width - 2
    inner_height = height - 2

    helper.draw_rect(pixels, x, y, width, height, BLACK)
    helper.draw_rect(pixels, x, y, width, 1, WHITE)
    helper.draw_rect(pixels, x, y + height - 1, width, 1, WHITE)
    helper.draw_rect(pixels, x, y, 1, height, WHITE)
    helper.draw_rect(pixels, x + width - 1, y, 1, height, WHITE)

    filled = round(inner_width * max(0.0, min(100.0, cpu)) / 100.0)
    if filled > 0:
        helper.draw_rect(pixels, x + 1, y + 1, filled, inner_height, cpu_bar_color(cpu))


def render_frame(
    title: str,
    cpu: float,
    mem_used_mib: float,
    mem_total_mib: float,
    temp_c: float | None,
) -> list[int]:
    helper = get_helper()
    pixels = [BLACK] * (WIDTH * HEIGHT)
    helper.fill(pixels, BLACK)

    helper.draw_text(pixels, 8, 4, title.upper(), CYAN, 2)
    helper.draw_text(pixels, 8, 22, f"CPU {cpu:5.1f}%", WHITE, 2)
    draw_cpu_bar(helper, pixels, cpu)

    mem_text = f"MEM {format_gib_value(mem_used_mib)}/{format_gib_value(mem_total_mib)}G"
    mem_scale = 2 if len(mem_text) <= 12 else 1
    helper.draw_text(pixels, 8, 48, mem_text, CYAN, mem_scale)

    temp_text = "TMP --.-C" if temp_c is None else f"TMP {temp_c:5.1f}C"
    helper.draw_text(pixels, 8, 64, temp_text, temp_color(temp_c), 2)
    return pixels


def open_display(args: argparse.Namespace):
    helper = get_helper()
    return helper.LcdSt7735(args.spi, args.reset_line, args.dc_line, args.gpio_mode, args.speed_hz)


def missing_gpio_note(helper) -> str:
    if helper.apt_package_installed("gpiod") or helper.apt_package_installed("python3-libgpiod"):
        return (
            f"gpiod or python3-libgpiod is installed for the system Python, but active Python "
            f"{sys.executable} cannot see it and gpioset is not in PATH; run with /usr/bin/python3, "
            "deactivate Conda/base, or fix PATH/Python environment"
        )
    return "install with: sudo apt install gpiod python3-libgpiod"


def print_status(args: argparse.Namespace) -> None:
    helper = get_helper()
    spi_node = Path(args.spi)
    spidev_ok = helper.module_available("spidev")
    gpiod_ok = helper.module_available("gpiod")
    gpioset_ok = helper.command_available("gpioset")
    temp_source, temp_value = probe_cpu_temperature()

    print("display=ST7735_160x80")
    print(f"python_executable={sys.executable}")
    print(f"helper_path={helper_path_label()}")
    print(f"required_overlay={SPI_LCD_OVERLAY}")
    print(f"overlay_config={OVERLAY_CONFIG}")
    print(f"overlay_dir={OVERLAY_DIR}")
    print(f"spi_device={args.spi}")
    print(f"spi_device_node={'present' if spi_node.exists() else 'missing'}")
    print(f"reset_line={args.reset_line}")
    print(f"dc_line={args.dc_line}")
    print("required_python_module_spidev=" + ("present" if spidev_ok else "missing"))
    print("optional_python_module_gpiod=" + ("present" if gpiod_ok else "missing"))
    print("command_gpioset=" + ("present" if gpioset_ok else "missing"))
    print("system_cpu_source=/proc/stat")
    print("system_memory_source=/proc/meminfo")
    print(
        "cpu_temp_source="
        + (temp_source if temp_source is not None else "unavailable")
        + (f" value={temp_value:0.1f}C" if temp_value is not None else "")
    )
    print("note=spi1-lcd shares pins with other functions; avoid ext-board-codec or I2C6 conflicts on PIN25/PIN26")
    print(f"spi_lcd_ready={'yes' if spi_node.exists() and spidev_ok and (gpiod_ok or gpioset_ok) else 'no'}")
    if not spi_node.exists():
        print(f"missing_node_note=enable {SPI_LCD_OVERLAY} in fdt_overlays and reboot")
    if not spidev_ok:
        print("missing_dependency_note=" + helper.missing_spidev_message())
    if not (gpiod_ok or gpioset_ok):
        print("missing_gpio_dependency_note=" + missing_gpio_note(helper))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spi", default=DEFAULT_SPI_DEVICE, help=f"SPI device path, default: {DEFAULT_SPI_DEVICE}")
    parser.add_argument(
        "--reset-line",
        default=DEFAULT_RESET_LINE,
        help=f"reset GPIO line name, default: {DEFAULT_RESET_LINE}",
    )
    parser.add_argument(
        "--dc-line",
        default=DEFAULT_DC_LINE,
        help=f"dc GPIO line name, default: {DEFAULT_DC_LINE}",
    )
    parser.add_argument(
        "--gpio-mode",
        choices=("auto", "gpiod", "gpioset"),
        default="auto",
        help="GPIO backend for the panel control lines",
    )
    parser.add_argument(
        "--speed-hz",
        type=int,
        default=DEFAULT_SPEED_HZ,
        help=f"SPI clock in Hz, default: {DEFAULT_SPEED_HZ}",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="refresh interval in seconds, default: 1.0",
    )
    parser.add_argument(
        "--title",
        default="VIM 5 SYS",
        help="title text on the first line",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="draw one frame and exit",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="print SPI LCD readiness and exit",
    )
    return parser


def run(args: argparse.Namespace) -> int:
    stop = False

    def handle_signal(signum: int, frame: object) -> None:
        del signum, frame
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    lcd = open_display(args)
    try:
        lcd.init()
        previous_cpu = read_cpu_ticks()
        while not stop:
            time.sleep(args.interval)
            current_cpu = read_cpu_ticks()
            cpu = cpu_percent(previous_cpu, current_cpu)
            previous_cpu = current_cpu
            mem_used_mib, mem_total_mib, _ = read_memory_stats()
            temp_c = read_cpu_temperature()
            lcd.flush(render_frame(args.title, cpu, mem_used_mib, mem_total_mib, temp_c))
            if args.once:
                break
    finally:
        lcd.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.status:
            print_status(args)
            return 0
        return run(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"spi_lcd_sys_monitor.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
