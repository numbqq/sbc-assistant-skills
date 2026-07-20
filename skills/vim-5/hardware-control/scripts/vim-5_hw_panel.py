#!/usr/bin/env python3
from __future__ import annotations

import argparse
import array
import fcntl
import os
import select
import shutil
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


LED_PATH = Path("/sys/class/leds/pwmled")
EXPANSION_GREEN_LED_PATH = Path("/sys/class/leds/green_led")
FAN_SCRIPT = Path("/usr/local/bin/fan.sh")
IIO_DEVICE = Path("/sys/bus/iio/devices/iio:device0")
I2C_DEV_ROOT = Path("/dev")
SPI_DEVICE = Path("/dev/spidev1.0")
UART_DEVICE = Path("/dev/ttyS4")
FUNC_KEY_DEVICE = Path("/dev/input/event3")
FUNC_KEY_NAME = "adc_keypad"
OVERLAY_CONFIG = "/boot/dtb/amlogic/kvim-5.dtb.overlay.env"
OVERLAY_DIR = "/boot/dtb/amlogic/kvim-5.dtb.overlays"
EXT_BOARD_CODEC_OVERLAY = "ext-board-codec"
SPI_LCD_OVERLAY = "spi1-lcd"
SPI_LCD_HELPER = Path(__file__).with_name("spi_lcd_st7735.py")
SPI_LCD_HELPER_REPO_PATH = "skills/vim-5/hardware-control/scripts/spi_lcd_st7735.py"
SPI_LCD_DEPENDENCIES = "python3-spidev gpiod python3-libgpiod"
ANALOG_MIC_DEVICE = "hw:0,1"
MIC_ARRAY_DEVICE = "hw:0,3"


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


def command_status(name: str, command: str) -> StatusItem:
    resolved = shutil.which(command)
    if resolved is None:
        return StatusItem(name, "missing", f"missing command: {command}")
    return StatusItem(name, "ready", resolved)


ADC_CHANNELS = {
    0: {"pin": "PIN10", "name": "ADC0", "iio_channel": 0, "wpi_pin": 19},
    1: {"pin": "PIN12", "name": "ADC1", "iio_channel": 3, "wpi_pin": 20},
    3: {"pin": "PIN12", "name": "ADC1", "iio_channel": 3, "wpi_pin": 20},
}


def adc_input_path(channel: int, iio_device: Path = IIO_DEVICE) -> Path:
    meta = ADC_CHANNELS[channel]
    return iio_device / f"in_voltage{meta['iio_channel']}_input"


def i2c_overlay_for_bus(bus: int) -> str:
    return {3: "i2c_d", 6: "i2c_g"}.get(bus, "unknown")


def i2c_pins_for_bus(bus: int) -> str:
    return {3: "PIN22/PIN23", 6: "PIN25/PIN26"}.get(bus, "unknown pins")


def i2c_status(bus: int, dev_root: Path = I2C_DEV_ROOT) -> StatusItem:
    node = dev_root / f"i2c-{bus}"
    if node.exists():
        return StatusItem(f"I2C{bus}", "ready", str(node))
    overlay = i2c_overlay_for_bus(bus)
    pins = i2c_pins_for_bus(bus)
    return StatusItem(
        f"I2C{bus}",
        "missing",
        f"missing {node}; enable {overlay} for {pins} in {OVERLAY_CONFIG}; overlays live in {OVERLAY_DIR}; reboot",
    )


def read_int_file(path: Path) -> int:
    return int(path.read_text(encoding="ascii").strip(), 0)


def read_adc_sample(
    channel: int,
    iio_device: Path = IIO_DEVICE,
) -> dict[str, object]:
    path = adc_input_path(channel, iio_device)
    meta = ADC_CHANNELS[channel]
    try:
        input_value = path.read_text(encoding="ascii").strip()
    except FileNotFoundError:
        return {
            "channel": channel,
            "pin": meta["pin"],
            "name": meta["name"],
            "iio_channel": meta["iio_channel"],
            "wpi_pin": meta["wpi_pin"],
            "state": "missing",
            "detail": f"missing {path}",
        }
    except PermissionError:
        return {
            "channel": channel,
            "pin": meta["pin"],
            "name": meta["name"],
            "iio_channel": meta["iio_channel"],
            "wpi_pin": meta["wpi_pin"],
            "state": "permission denied",
            "detail": f"permission denied reading {path}",
        }
    return {
        "channel": channel,
        "pin": meta["pin"],
        "name": meta["name"],
        "iio_channel": meta["iio_channel"],
        "wpi_pin": meta["wpi_pin"],
        "state": "ready",
        "input": input_value,
        "detail": str(path),
    }


def spi_status(device: Path = SPI_DEVICE) -> StatusItem:
    if device.exists():
        return StatusItem("SPI1", "ready", str(device))
    return StatusItem(
        "SPI1",
        "missing",
        f"missing {device}; enable spi1 for PIN25/PIN26/PIN36/PIN37 in {OVERLAY_CONFIG}; overlays live in {OVERLAY_DIR}; reboot",
    )


def uart_status(device: Path = UART_DEVICE) -> StatusItem:
    if device.exists():
        return StatusItem("UART_AO_E", "ready", str(device))
    return StatusItem(
        "UART_AO_E",
        "missing",
        f"missing {device}; enable uart_ao_e for PIN15/PIN16 in {OVERLAY_CONFIG}; overlays live in {OVERLAY_DIR}; reboot",
    )


def render_status_items(title: str, items: list[StatusItem]) -> str:
    lines = [title, ""]
    for item in items:
        lines.append(f"{item.name:12} {item.state:17} {item.detail}")
    return "\n".join(lines)


def board_status_items() -> list[StatusItem]:
    return [
        path_status("LED", LED_PATH),
        path_status("Green LED", EXPANSION_GREEN_LED_PATH),
        path_status("Fan", FAN_SCRIPT, require_exec=True),
        path_status("ADC0", adc_input_path(0), require_read=True),
        path_status("ADC1", adc_input_path(1), require_read=True),
        i2c_status(3),
        i2c_status(6),
        spi_status(),
        uart_status(),
        func_key_status(),
    ]


def render_board_status() -> str:
    return render_status_items("Board Status", board_status_items())


def render_adc_monitor() -> str:
    lines = ["ADC Monitor", "", "Values are driver-reported IIO input readings.", ""]
    for channel in (0, 1):
        sample = read_adc_sample(channel)
        if sample["state"] == "ready":
            lines.append(
                f"{sample['pin']} {sample['name']}: input={sample['input']} "
                f"iio_channel={sample['iio_channel']} gpio_aread={sample['wpi_pin']}"
            )
        else:
            lines.append(f"{sample['pin']} {sample['name']}: {sample['state']} {sample['detail']}")
    return "\n".join(lines)


def render_gpio_pwm_map() -> str:
    return """GPIO/PWM Map (read-only)

Use the wPi column with wiringpi commands such as gpio mode/read/write/pwm.

Physical  wPi  GPIO  Name       Notes
10        19         ADC0       ADC-only, read via in_voltage0_input or gpio aread 19
12        20         ADC1       ADC-only, read via in_voltage3_input or gpio aread 20
13        1    641   PIN.D13    GPIO by default; SPDIF when spdifout is active
15        2    637   PIN.D9     GPIO by default; UART RX when uart_ao_e is active
16        3    636   PIN.D8     GPIO by default; UART TX when uart_ao_e is active
18        4    629   PIN.D1     Alternate function by default
19        5    628   PIN.D0     Alternate function by default
22        6    591   PIN.A15    GPIO by default; I2C3 when i2c_d is active
23        7    590   PIN.A14    GPIO by default; I2C3 when i2c_d is active
25        8    555   PIN.M1     GPIO by default; I2C6 when i2c_g is active; shared with SPI1
26        9    554   PIN.M0     GPIO by default; I2C6 when i2c_g is active; shared with SPI1
29        10   577   PIN.A1     GPIO input by default
30        11   576   PIN.A0     GPIO input by default
31        12   579   PIN.A3     GPIO input by default
32        13   578   PIN.A2     GPIO input by default
33        14   580   PIN.A4     GPIO input by default
35        15   601   PIN.Y5     GPIO by default; PWM when pwm_j is active
36        16   556   PIN.M2     GPIO by default; SPI1 when spi1 is active
37        17   557   PIN.M3     GPIO by default; SPI1 when spi1 is active
39        18   633   PIN.D5     GPIO by default; IR when ir is active

This panel does not perform arbitrary GPIO or PWM writes.
"""


def render_bus_status(dev_root: Path = I2C_DEV_ROOT) -> str:
    return render_status_items(
        "I2C/SPI/UART Status",
        [
            i2c_status(3, dev_root),
            i2c_status(6, dev_root),
            spi_status(dev_root / SPI_DEVICE.name),
            uart_status(dev_root / UART_DEVICE.name),
        ],
    )


def spi_lcd_status(
    device: Path = SPI_DEVICE,
    helper_path: Path = SPI_LCD_HELPER,
    helper_label: str = SPI_LCD_HELPER_REPO_PATH,
) -> StatusItem:
    helper = f"helper present {helper_label}" if helper_path.exists() else f"helper missing {helper_label}"
    conflict = "avoid ext-board-codec/I2S/SPI overlay conflicts on shared pins"
    deps = f"apt install {SPI_LCD_DEPENDENCIES}"
    if device.exists():
        return StatusItem(
            "SPI LCD/OLED",
            "ready",
            f"{device}; overlay {SPI_LCD_OVERLAY}; {helper}; {deps}; {conflict}",
        )
    return StatusItem(
        "SPI LCD/OLED",
        "missing",
        f"missing {device}; enable {SPI_LCD_OVERLAY} in {OVERLAY_CONFIG}; overlays live in {OVERLAY_DIR}; {helper}; {deps}; {conflict}",
    )


def expansion_board_status_items() -> list[StatusItem]:
    analog_route = "amixer -c 0 cset name='TDMIN_B source select' 'tdmin_b'"
    analog_record = "arecord -D hw:0,1 -f cd -c 2 -d 10 test.wav"
    array_record = "arecord -Dhw:0,3 -r 48000 -f S16_LE -c 6 -d 10 pdm_6ch.wav"
    return [
        path_status("Green LED", EXPANSION_GREEN_LED_PATH),
        StatusItem(
            "Analog MIC",
            "requires overlay",
            f"{EXT_BOARD_CODEC_OVERLAY}; device {ANALOG_MIC_DEVICE}; {analog_route}; {analog_record}; shares pins with I2S/SPI",
        ),
        command_status("amixer", "amixer"),
        command_status("arecord", "arecord"),
        StatusItem("Mic Array", "record", f"device {MIC_ARRAY_DEVICE}; {array_record}"),
        spi_lcd_status(),
    ]


def render_expansion_board_status() -> str:
    return render_status_items("Expansion Board Status", expansion_board_status_items())


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
    return """VIM 5 Hardware Panel

[1] Board Status
[2] ADC Monitor
[3] LED Control
[4] Fan Control
[5] GPIO/PWM Map
[6] I2C/SPI/UART Status
[7] OLED Status Display
[8] Func Key Status
[9] Expansion Board Status
[q] Quit
"""


def parse_int_auto(value: str) -> int:
    return int(value, 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive Khadas VIM 5 hardware panel.")
    parser.add_argument("--no-key", action="store_true", help="disable optional Func key polling")
    parser.add_argument("--oled", action="store_true", help="enable optional SSD1306 OLED status output")
    parser.add_argument("--i2c-bus", type=int, default=3, help="OLED I2C bus, default: 3")
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


def oled_summary_text(cpu_percent: float, memory_percent: float, adc0: str, adc1: str) -> str:
    return "\n".join(
        [
            f"CPU {cpu_percent:.0f}%",
            f"MEM {memory_percent:.0f}%",
            f"ADC0 {adc0}",
            f"ADC1 {adc1}",
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


def adc_input_for_oled(channel: int) -> str:
    sample = read_adc_sample(channel)
    if sample["state"] != "ready":
        return "NA"
    return str(sample["input"])


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
        adc0=adc_input_for_oled(0),
        adc1=adc_input_for_oled(1),
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


def render_oled_status(
    enabled: bool = False,
    bus: int = 5,
    addr: int = 0x3C,
    dev_root: Path = I2C_DEV_ROOT,
) -> str:
    lines = ["OLED Status Display", ""]
    if not enabled:
        lines.append("OLED disabled")
        lines.append(f"Use --oled --i2c-bus {bus} --oled-addr 0x{addr:x} to enable SSD1306 updates.")
        return "\n".join(lines)
    result = update_oled_status(True, bus, addr, dev_root=dev_root)
    lines.append(f"OLED update: {result}")
    return "\n".join(lines)


def render_page(selection: str, args: argparse.Namespace | None = None) -> str:
    def oled_page() -> str:
        if args is None:
            return render_oled_status()
        return render_oled_status(True, args.i2c_bus, args.oled_addr)

    pages = {
        "1": render_board_status,
        "2": render_adc_monitor,
        "3": render_led_control,
        "4": render_fan_control,
        "5": render_gpio_pwm_map,
        "6": render_bus_status,
        "7": oled_page,
        "8": render_func_key_status,
        "9": render_expansion_board_status,
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
            elif selection in {"1", "2", "5", "6", "7", "8", "9"}:
                clear_screen()
                print(render_page(selection, args))
                prompt_input("\nPress Enter to return...")
            else:
                print(render_page(selection, args))
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
