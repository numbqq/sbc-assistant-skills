#!/usr/bin/env python3
from __future__ import annotations

import argparse
import array
import fcntl
import os
import select
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


LED_PATH = Path("/sys/class/leds/pwmled")
FAN_SCRIPT = Path("/usr/local/bin/fan.sh")
IIO_DEVICE = Path("/sys/bus/iio/devices/iio:device0")
I2C_DEV_ROOT = Path("/dev")
SPI_DEVICE = Path("/dev/spidev1.0")
UART_DEVICE = Path("/dev/ttyS4")
FUNC_KEY_DEVICE = Path("/dev/input/event2")
FUNC_KEY_NAME = "adc_keypad"
OVERLAY_CONFIG = "/boot/dtb/amlogic/kvim4.dtb.overlay.env"


@dataclass(frozen=True)
class StatusItem:
    name: str
    state: str
    detail: str


def path_status(
    name: str,
    path: Path,
    require_read: bool = False,
    require_exec: bool = False,
) -> StatusItem:
    if not path.exists():
        return StatusItem(name, "missing", f"missing {path}")
    if require_read and not os.access(path, os.R_OK):
        return StatusItem(name, "permission denied", f"permission denied reading {path}")
    if require_exec and not os.access(path, os.X_OK):
        return StatusItem(name, "permission denied", f"permission denied executing {path}")
    return StatusItem(name, "ready", str(path))


def adc_raw_path(channel: int, iio_device: Path = IIO_DEVICE) -> Path:
    return iio_device / f"in_voltage{channel}_raw"


def i2c_overlay_for_bus(bus: int) -> str:
    return {5: "i2cm_f", 0: "i2cm_a"}.get(bus, "unknown")


def i2c_pins_for_bus(bus: int) -> str:
    return {5: "PIN22/PIN23", 0: "PIN25/PIN26"}.get(bus, "unknown pins")


def i2c_status(bus: int, dev_root: Path = I2C_DEV_ROOT) -> StatusItem:
    node = dev_root / f"i2c-{bus}"
    if node.exists():
        return StatusItem(f"I2C{bus}", "ready", str(node))
    overlay = i2c_overlay_for_bus(bus)
    pins = i2c_pins_for_bus(bus)
    return StatusItem(
        f"I2C{bus}",
        "missing",
        f"missing {node}; enable {overlay} for {pins} in {OVERLAY_CONFIG} and reboot",
    )


ADC_CHANNELS = {
    6: ("PIN10", "ADC_CH6"),
    3: ("PIN12", "ADC_CH3"),
}
DEFAULT_RAW_MAX = 4095
DEFAULT_VREF = 1.8


def read_int_file(path: Path) -> int:
    return int(path.read_text(encoding="ascii").strip(), 0)


def read_adc_sample(
    channel: int,
    iio_device: Path = IIO_DEVICE,
    raw_max: int = DEFAULT_RAW_MAX,
    vref: float = DEFAULT_VREF,
) -> dict[str, object]:
    path = adc_raw_path(channel, iio_device)
    pin, name = ADC_CHANNELS[channel]
    try:
        raw = read_int_file(path)
    except FileNotFoundError:
        return {
            "channel": channel,
            "pin": pin,
            "name": name,
            "state": "missing",
            "detail": f"missing {path}",
        }
    except PermissionError:
        return {
            "channel": channel,
            "pin": pin,
            "name": name,
            "state": "permission denied",
            "detail": f"permission denied reading {path}",
        }
    voltage = raw * vref / raw_max
    return {
        "channel": channel,
        "pin": pin,
        "name": name,
        "state": "ready",
        "raw": raw,
        "voltage": f"{voltage:.3f}V estimated",
        "detail": str(path),
    }


def spi_status(device: Path = SPI_DEVICE) -> StatusItem:
    if device.exists():
        return StatusItem("SPI0", "ready", str(device))
    return StatusItem(
        "SPI0",
        "missing",
        f"missing {device}; enable spi0 for PIN25/PIN26/PIN36/PIN37 in {OVERLAY_CONFIG} and reboot",
    )


def uart_status(device: Path = UART_DEVICE) -> StatusItem:
    if device.exists():
        return StatusItem("UART_E", "ready", str(device))
    return StatusItem(
        "UART_E",
        "missing",
        f"missing {device}; enable uart_e for PIN15/PIN16 in {OVERLAY_CONFIG} and reboot",
    )


def render_status_items(title: str, items: list[StatusItem]) -> str:
    lines = [title, ""]
    for item in items:
        lines.append(f"{item.name:12} {item.state:17} {item.detail}")
    return "\n".join(lines)


def board_status_items() -> list[StatusItem]:
    return [
        path_status("LED", LED_PATH),
        path_status("Fan", FAN_SCRIPT, require_exec=True),
        path_status("ADC_CH6", adc_raw_path(6), require_read=True),
        path_status("ADC_CH3", adc_raw_path(3), require_read=True),
        i2c_status(5),
        i2c_status(0),
        spi_status(),
        uart_status(),
        func_key_status(),
    ]


def render_board_status() -> str:
    return render_status_items("Board Status", board_status_items())


def render_adc_monitor() -> str:
    lines = ["ADC Monitor", "", "Voltage uses 12-bit/1.8V default and is an estimate.", ""]
    for channel in (6, 3):
        sample = read_adc_sample(channel)
        if sample["state"] == "ready":
            lines.append(
                f"{sample['pin']} {sample['name']}: raw={sample['raw']} voltage={sample['voltage']}"
            )
        else:
            lines.append(f"{sample['pin']} {sample['name']}: {sample['state']} {sample['detail']}")
    return "\n".join(lines)


def render_gpio_pwm_map() -> str:
    return """GPIO/PWM Map (read-only)

Use the wPi column with wiringpi commands such as gpio mode/read/write/pwm.

Physical  wPi  GPIO  Name       Notes
10        19         ADC_CH6    ADC-only, read via in_voltage6_raw, not digital output
12        20         ADC_CH3    ADC-only, read via in_voltage3_raw, not digital output
15        2    491   PIN.Y7     GPIO by default; UART_E RX when uart_e is active
16        3    490   PIN.Y6     GPIO by default; UART_E TX when uart_e is active
22        6    501   PIN.Y17    GPIO by default; I2C5 when i2cm_f is active
23        7    502   PIN.Y18    GPIO by default; I2C5 when i2cm_f is active
25        8    466   PIN.T20    GPIO by default; I2C0 when i2cm_a is active; shared with SPI0
26        9    467   PIN.T21    GPIO by default; I2C0 when i2cm_a is active; shared with SPI0
36        16   464   PIN.T18    GPIO by default; SPI0 when spi0 is active
37        17   465   PIN.T19    GPIO by default; SPI0 when spi0 is active

This panel does not perform arbitrary GPIO or PWM writes.
"""


def render_bus_status(dev_root: Path = I2C_DEV_ROOT) -> str:
    return render_status_items(
        "I2C/SPI/UART Status",
        [i2c_status(5, dev_root), i2c_status(0, dev_root), spi_status(), uart_status()],
    )


FAN_ACTIONS = {"auto", "off", "low", "mid", "high", "temp", "mode"}


def led_values(led_path: Path = LED_PATH) -> tuple[int, int]:
    brightness = read_int_file(led_path / "brightness")
    max_brightness = read_int_file(led_path / "max_brightness")
    return brightness, max_brightness


def set_led_brightness(value: int, led_path: Path = LED_PATH) -> None:
    _current, max_brightness = led_values(led_path)
    if value < 0 or value > max_brightness:
        raise ValueError(f"brightness must be 0..{max_brightness}")
    try:
        (led_path / "brightness").write_text(f"{value}\n", encoding="ascii")
    except PermissionError as exc:
        raise PermissionError("permission denied writing LED brightness; try sudo") from exc


def run_fan_action(action: str, fan_script: Path = FAN_SCRIPT) -> str:
    if action not in FAN_ACTIONS:
        raise ValueError(f"unsupported fan action: {action}")
    if not fan_script.exists():
        raise FileNotFoundError(f"missing fan script: {fan_script}")
    completed = subprocess.run(
        [str(fan_script), action],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = (completed.stdout + completed.stderr).strip()
    if completed.returncode != 0:
        raise RuntimeError(output or f"fan action failed: {action}")
    return output or f"fan action complete: {action}"


EV_KEY = 0x01
INPUT_EVENT_FORMAT = "llHHi"
INPUT_EVENT_SIZE = struct.calcsize(INPUT_EVENT_FORMAT)


def eviocgname_request(length: int) -> int:
    return 0x80000000 | (length << 16) | (ord("E") << 8) | 0x06


def input_device_name(fd: int) -> str:
    length = 256
    buf = array.array("b", [0] * length)
    fcntl.ioctl(fd, eviocgname_request(length), buf, True)
    return buf.tobytes().split(b"\0", 1)[0].decode("utf-8", errors="replace")


def parse_func_key_action(data: bytes) -> str | None:
    if len(data) != INPUT_EVENT_SIZE:
        return None
    _seconds, _microseconds, event_type, _code, value = struct.unpack(INPUT_EVENT_FORMAT, data)
    if event_type != EV_KEY:
        return None
    return {0: "release", 1: "press", 2: "repeat"}.get(value)


def open_func_key_for_auxiliary(
    disabled: bool,
    device: Path = FUNC_KEY_DEVICE,
) -> int | None:
    if disabled or not device.exists():
        return None
    try:
        fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if input_device_name(fd) == FUNC_KEY_NAME:
            return fd
    except OSError:
        pass
    os.close(fd)
    return None


def poll_func_key_action(fd: int | None) -> str | None:
    if fd is None:
        return None
    ready, _, _ = select.select([fd], [], [], 0)
    if not ready:
        return None
    try:
        return parse_func_key_action(os.read(fd, INPUT_EVENT_SIZE))
    except OSError:
        return None


def func_key_status(device: Path = FUNC_KEY_DEVICE) -> StatusItem:
    if not device.exists():
        return StatusItem("Func key", "missing", f"missing {device}; expected {FUNC_KEY_NAME}")
    try:
        fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    except PermissionError:
        return StatusItem(
            "Func key",
            "permission denied",
            f"permission denied reading {device}; try sudo or add the user to the input group",
        )
    except OSError as exc:
        return StatusItem("Func key", "missing", f"cannot open {device}: {exc}; expected {FUNC_KEY_NAME}")
    try:
        name = input_device_name(fd)
    except OSError as exc:
        return StatusItem(
            "Func key",
            "missing",
            f"cannot read input name from {device}: {exc}; expected {FUNC_KEY_NAME}",
        )
    finally:
        os.close(fd)
    if name == FUNC_KEY_NAME:
        return StatusItem("Func key", "ready", f"{device} name={name}")
    return StatusItem("Func key", "missing", f"{device} name={name or 'unknown'}, expected {FUNC_KEY_NAME}")


def render_func_key_status() -> str:
    return render_status_items("Func Key Status", [func_key_status()])


def render_main_menu() -> str:
    return """VIM4 Hardware Panel

[1] Board Status
[2] ADC Monitor
[3] LED Control
[4] Fan Control
[5] GPIO/PWM Map
[6] I2C/SPI/UART Status
[7] OLED Status Display
[8] Func Key Status
[q] Quit
"""


def parse_int_auto(value: str) -> int:
    return int(value, 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive Khadas VIM4 hardware panel.")
    parser.add_argument("--no-key", action="store_true", help="disable optional Func key polling")
    parser.add_argument("--oled", action="store_true", help="enable optional SSD1306 OLED status output")
    parser.add_argument("--i2c-bus", type=int, default=5, help="OLED I2C bus, default: 5")
    parser.add_argument(
        "--oled-addr",
        type=parse_int_auto,
        default=0x3C,
        help="OLED I2C address, default: 0x3c",
    )
    return parser


def render_led_control() -> str:
    try:
        brightness, max_brightness = led_values()
        return (
            "LED Control\n\n"
            f"brightness={brightness}\n"
            f"max_brightness={max_brightness}\n\n"
            f"Enter a value from 0..{max_brightness}, or b to go back."
        )
    except Exception as exc:
        return f"LED Control\n\n{exc}"


def render_fan_control() -> str:
    return "Fan Control\n\nActions: auto off low mid high temp mode\nEnter an action, or b to go back."


def oled_summary_text(cpu_percent: float, memory_percent: float, adc6: str, adc3: str) -> str:
    return "\n".join(
        [
            f"CPU {cpu_percent:.0f}%",
            f"MEM {memory_percent:.0f}%",
            f"ADC6 {adc6}",
            f"ADC3 {adc3}",
        ]
    )


def read_cpu_percent() -> float:
    with open("/proc/stat", "r", encoding="ascii") as stat:
        fields = [int(value) for value in stat.readline().split()[1:]]
    idle = fields[3] + fields[4]
    total = sum(fields)
    time.sleep(0.05)
    with open("/proc/stat", "r", encoding="ascii") as stat:
        next_fields = [int(value) for value in stat.readline().split()[1:]]
    next_idle = next_fields[3] + next_fields[4]
    next_total = sum(next_fields)
    total_delta = next_total - total
    idle_delta = next_idle - idle
    if total_delta <= 0:
        return 0.0
    return 100.0 * (total_delta - idle_delta) / total_delta


def read_memory_percent() -> float:
    info: dict[str, int] = {}
    with open("/proc/meminfo", "r", encoding="ascii") as meminfo:
        for line in meminfo:
            key, raw_value = line.split(":", 1)
            info[key] = int(raw_value.strip().split()[0])
    total = info["MemTotal"]
    available = info.get("MemAvailable", info.get("MemFree", 0))
    if total <= 0:
        return 0.0
    return 100.0 * (total - available) / total


class SSD1306TextDisplay:
    width = 128
    pages = 8
    font = {
        " ": [0x00, 0x00, 0x00, 0x00, 0x00],
        "%": [0x23, 0x13, 0x08, 0x64, 0x62],
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
        "C": [0x3E, 0x41, 0x41, 0x41, 0x22],
        "D": [0x7F, 0x41, 0x41, 0x22, 0x1C],
        "E": [0x7F, 0x49, 0x49, 0x49, 0x41],
        "M": [0x7F, 0x02, 0x0C, 0x02, 0x7F],
        "N": [0x7F, 0x04, 0x08, 0x10, 0x7F],
        "P": [0x7F, 0x09, 0x09, 0x09, 0x06],
        "U": [0x3F, 0x40, 0x40, 0x40, 0x3F],
    }

    def __init__(self, bus: int, addr: int, dev_root: Path = I2C_DEV_ROOT) -> None:
        self.path = dev_root / f"i2c-{bus}"
        self.addr = addr
        self.fd = os.open(self.path, os.O_RDWR)
        fcntl.ioctl(self.fd, 0x0703, addr)

    def close(self) -> None:
        os.close(self.fd)

    def write(self, control: int, values: list[int]) -> None:
        os.write(self.fd, bytes([control, *values]))

    def command(self, *values: int) -> None:
        self.write(0x00, list(values))

    def init(self) -> None:
        for command in (0xAE, 0xA4, 0xA6, 0xAF):
            self.command(command)

    def clear(self) -> None:
        for page in range(self.pages):
            self.command(0xB0 | page, 0x00, 0x10)
            for _ in range(8):
                self.write(0x40, [0x00] * 16)

    def draw_text(self, text: str) -> None:
        self.clear()
        for page, line in enumerate(text.splitlines()[: self.pages]):
            self.command(0xB0 | page, 0x00, 0x10)
            data: list[int] = []
            for char in line.upper():
                data.extend(self.font.get(char, self.font[" "]))
                data.append(0x00)
            data = data[: self.width] + [0x00] * max(0, self.width - len(data))
            for start in range(0, self.width, 16):
                self.write(0x40, data[start : start + 16])


def adc_raw_for_oled(channel: int) -> str:
    sample = read_adc_sample(channel)
    if sample["state"] != "ready":
        return "NA"
    return str(sample["raw"])


def build_oled_summary() -> str:
    try:
        cpu_percent = read_cpu_percent()
    except OSError:
        cpu_percent = 0.0
    try:
        memory_percent = read_memory_percent()
    except OSError:
        memory_percent = 0.0
    return oled_summary_text(
        cpu_percent=cpu_percent,
        memory_percent=memory_percent,
        adc6=adc_raw_for_oled(6),
        adc3=adc_raw_for_oled(3),
    )


def update_oled_status(
    enabled: bool,
    bus: int,
    addr: int,
    dev_root: Path = I2C_DEV_ROOT,
    display_cls: type[SSD1306TextDisplay] = SSD1306TextDisplay,
) -> str:
    if not enabled:
        return "OLED disabled"
    node = dev_root / f"i2c-{bus}"
    if not node.exists():
        return f"missing {node}; enable the matching I2C overlay and reboot"
    try:
        display = display_cls(bus, addr, dev_root=dev_root)
    except PermissionError:
        return f"permission denied opening {node}; try sudo"
    except OSError as exc:
        return f"cannot open {node}: {exc}"
    try:
        display.init()
        display.draw_text(build_oled_summary())
    finally:
        display.close()
    return "OLED status updated"


def render_oled_status() -> str:
    return "OLED Status Display\n\nUse --oled --i2c-bus 5 --oled-addr 0x3c to enable SSD1306 updates."


def render_page(selection: str) -> str:
    pages = {
        "1": render_board_status,
        "2": render_adc_monitor,
        "3": render_led_control,
        "4": render_fan_control,
        "5": render_gpio_pwm_map,
        "6": render_bus_status,
        "7": render_oled_status,
        "8": render_func_key_status,
    }
    renderer = pages.get(selection)
    if renderer is None:
        return f"Unknown selection: {selection}"
    return renderer()


def clear_screen() -> None:
    print("\033[2J\033[H", end="")


def prompt_input(prompt: str) -> str:
    return input(prompt).strip()


def handle_led_page() -> None:
    while True:
        clear_screen()
        print(render_led_control())
        value = prompt_input("LED> ")
        if value in {"b", "q"}:
            return
        try:
            set_led_brightness(int(value, 0))
            print("LED brightness updated.")
        except Exception as exc:
            print(exc)
        prompt_input("Press Enter to continue...")


def handle_fan_page() -> None:
    while True:
        clear_screen()
        print(render_fan_control())
        action = prompt_input("Fan> ")
        if action in {"b", "q"}:
            return
        try:
            print(run_fan_action(action))
        except Exception as exc:
            print(exc)
        prompt_input("Press Enter to continue...")


def run_interactive(args: argparse.Namespace) -> int:
    update_oled_status(args.oled, args.i2c_bus, args.oled_addr)
    key_fd = open_func_key_for_auxiliary(args.no_key)
    try:
        while True:
            clear_screen()
            print(render_main_menu())
            selection = prompt_input("> ")
            if poll_func_key_action(key_fd) == "press":
                selection = "1"
            if selection == "q":
                return 0
            if selection == "3":
                handle_led_page()
            elif selection == "4":
                handle_fan_page()
            elif selection in {"1", "2", "5", "6", "7", "8"}:
                clear_screen()
                print(render_page(selection))
                prompt_input("\nPress Enter to return...")
            else:
                print(render_page(selection))
                prompt_input("Press Enter to continue...")
    finally:
        if key_fd is not None:
            os.close(key_fd)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_interactive(args)
    except KeyboardInterrupt:
        print("")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
