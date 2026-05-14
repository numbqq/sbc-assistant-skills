# VIM4 Hardware Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `vim4_hw_panel.py`, a keyboard-first interactive VIM4 terminal hardware panel with conservative write controls.

**Architecture:** Add one self-contained Python standard-library script and one focused unittest module. Keep hardware access behind small functions so missing devices, permissions, and subprocess output can be tested without VIM4 hardware.

**Tech Stack:** Python 3 standard library, `unittest`, Linux sysfs/devfs paths, optional SSD1306 I2C writes through `fcntl.ioctl`.

---

## File Structure

- Create `skills/vim4/hardware-control/scripts/vim4_hw_panel.py`
  - Constants for VIM4 hardware paths and overlay guidance.
  - Pure status helpers for files, ADC, buses, UART, SPI, LED, fan, and Func key.
  - Page renderers that return strings.
  - Conservative control functions for LED brightness and fan actions.
  - Simple keyboard menu loop.
  - Optional OLED helper class and `--oled` update path.
- Create `tests/test_vim4_hw_panel.py`
  - Import the script by file path.
  - Test status helpers and page rendering using temporary paths and mocks.
  - Test LED validation without touching real sysfs.
  - Test fan command invocation using mocked `subprocess.run`.
  - Test CLI parser defaults.

### Task 1: Status Models and Device Checks

**Files:**
- Create: `tests/test_vim4_hw_panel.py`
- Create: `skills/vim4/hardware-control/scripts/vim4_hw_panel.py`

- [ ] **Step 1: Write failing tests for status helpers**

```python
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


HELPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "vim4"
    / "hardware-control"
    / "scripts"
    / "vim4_hw_panel.py"
)

spec = importlib.util.spec_from_file_location("vim4_hw_panel", HELPER_PATH)
vim4_hw_panel = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vim4_hw_panel
spec.loader.exec_module(vim4_hw_panel)


class HardwarePanelStatusTest(unittest.TestCase):
    def test_path_status_reports_ready_for_existing_readable_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "node"
            path.write_text("1\n", encoding="ascii")

            status = vim4_hw_panel.path_status("LED", path)

        self.assertEqual(status.name, "LED")
        self.assertEqual(status.state, "ready")
        self.assertEqual(status.detail, str(path))

    def test_path_status_reports_missing_for_absent_path(self):
        status = vim4_hw_panel.path_status("SPI0", Path("/missing/spidev1.0"))

        self.assertEqual(status.state, "missing")
        self.assertIn("/missing/spidev1.0", status.detail)

    def test_i2c_status_explains_missing_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = vim4_hw_panel.i2c_status(5, dev_root=Path(tmp))

        self.assertEqual(status.state, "missing")
        self.assertIn("i2cm_f", status.detail)
        self.assertIn("reboot", status.detail)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_vim4_hw_panel.HardwarePanelStatusTest -v`

Expected: FAIL or ERROR because `vim4_hw_panel.py` does not exist.

- [ ] **Step 3: Implement status helpers**

Create `vim4_hw_panel.py` with:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import array
import fcntl
import os
import select
import struct
import subprocess
import sys
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


def path_status(name: str, path: Path, require_read: bool = False, require_exec: bool = False) -> StatusItem:
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_vim4_hw_panel.HardwarePanelStatusTest -v`

Expected: PASS.

### Task 2: Read-Only Page Rendering

**Files:**
- Modify: `tests/test_vim4_hw_panel.py`
- Modify: `skills/vim4/hardware-control/scripts/vim4_hw_panel.py`

- [ ] **Step 1: Write failing tests for ADC and board status rendering**

Add tests:

```python
class HardwarePanelRenderTest(unittest.TestCase):
    def test_read_adc_reports_raw_and_estimated_voltage(self):
        with tempfile.TemporaryDirectory() as tmp:
            iio = Path(tmp)
            (iio / "in_voltage6_raw").write_text("2048\n", encoding="ascii")

            sample = vim4_hw_panel.read_adc_sample(6, iio_device=iio)

        self.assertEqual(sample["state"], "ready")
        self.assertEqual(sample["raw"], 2048)
        self.assertIn("0.900", sample["voltage"])

    def test_render_gpio_pwm_map_is_read_only(self):
        text = vim4_hw_panel.render_gpio_pwm_map()

        self.assertIn("read-only", text.lower())
        self.assertIn("wPi", text)
        self.assertIn("ADC_CH6", text)
        self.assertNotIn("Enter GPIO", text)

    def test_render_bus_status_includes_spi_and_uart_overlay_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = vim4_hw_panel.render_bus_status(dev_root=Path(tmp))

        self.assertIn("SPI0", text)
        self.assertIn("spi0", text)
        self.assertIn("UART_E", text)
        self.assertIn("uart_e", text)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_vim4_hw_panel.HardwarePanelRenderTest -v`

Expected: FAIL with missing functions.

- [ ] **Step 3: Implement rendering helpers**

Add functions:

```python
ADC_CHANNELS = {
    6: ("PIN10", "ADC_CH6"),
    3: ("PIN12", "ADC_CH3"),
}
DEFAULT_RAW_MAX = 4095
DEFAULT_VREF = 1.8


def read_int_file(path: Path) -> int:
    return int(path.read_text(encoding="ascii").strip(), 0)


def read_adc_sample(channel: int, iio_device: Path = IIO_DEVICE, raw_max: int = DEFAULT_RAW_MAX, vref: float = DEFAULT_VREF) -> dict[str, object]:
    path = adc_raw_path(channel, iio_device)
    pin, name = ADC_CHANNELS[channel]
    try:
        raw = read_int_file(path)
    except FileNotFoundError:
        return {"channel": channel, "pin": pin, "name": name, "state": "missing", "detail": f"missing {path}"}
    except PermissionError:
        return {"channel": channel, "pin": pin, "name": name, "state": "permission denied", "detail": f"permission denied reading {path}"}
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
    return StatusItem("SPI0", "missing", f"missing {device}; enable spi0 for PIN25/PIN26/PIN36/PIN37 in {OVERLAY_CONFIG} and reboot")


def uart_status(device: Path = UART_DEVICE) -> StatusItem:
    if device.exists():
        return StatusItem("UART_E", "ready", str(device))
    return StatusItem("UART_E", "missing", f"missing {device}; enable uart_e for PIN15/PIN16 in {OVERLAY_CONFIG} and reboot")


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
            lines.append(f"{sample['pin']} {sample['name']}: raw={sample['raw']} voltage={sample['voltage']}")
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
    return render_status_items("I2C/SPI/UART Status", [i2c_status(5, dev_root), i2c_status(0, dev_root), spi_status(), uart_status()])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_vim4_hw_panel.HardwarePanelRenderTest -v`

Expected: PASS.

### Task 3: LED and Fan Conservative Controls

**Files:**
- Modify: `tests/test_vim4_hw_panel.py`
- Modify: `skills/vim4/hardware-control/scripts/vim4_hw_panel.py`

- [ ] **Step 1: Write failing control tests**

Add tests:

```python
from unittest import mock


class HardwarePanelControlTest(unittest.TestCase):
    def test_set_led_brightness_rejects_value_above_max(self):
        with tempfile.TemporaryDirectory() as tmp:
            led = Path(tmp)
            (led / "max_brightness").write_text("1\n", encoding="ascii")
            (led / "brightness").write_text("0\n", encoding="ascii")

            with self.assertRaisesRegex(ValueError, "0..1"):
                vim4_hw_panel.set_led_brightness(2, led_path=led)

    def test_set_led_brightness_writes_valid_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            led = Path(tmp)
            (led / "max_brightness").write_text("3\n", encoding="ascii")
            brightness = led / "brightness"
            brightness.write_text("0\n", encoding="ascii")

            vim4_hw_panel.set_led_brightness(2, led_path=led)

            self.assertEqual(brightness.read_text(encoding="ascii"), "2\n")

    def test_run_fan_action_allows_only_skill_actions(self):
        with self.assertRaisesRegex(ValueError, "unsupported fan action"):
            vim4_hw_panel.run_fan_action("turbo")

    def test_run_fan_action_invokes_fan_script(self):
        completed = subprocess.CompletedProcess(["fan.sh", "mode"], 0, "mode=auto\n", "")
        with mock.patch.object(vim4_hw_panel.subprocess, "run", return_value=completed) as run:
            result = vim4_hw_panel.run_fan_action("mode", fan_script=Path("/tmp/fan.sh"))

        run.assert_called_once()
        self.assertIn("mode=auto", result)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_vim4_hw_panel.HardwarePanelControlTest -v`

Expected: FAIL with missing control functions.

- [ ] **Step 3: Implement LED and fan controls**

Add functions:

```python
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
        raise PermissionError(f"permission denied writing LED brightness; try sudo") from exc


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_vim4_hw_panel.HardwarePanelControlTest -v`

Expected: PASS.

### Task 4: Func Key Status and CLI/Menu Shell

**Files:**
- Modify: `tests/test_vim4_hw_panel.py`
- Modify: `skills/vim4/hardware-control/scripts/vim4_hw_panel.py`

- [ ] **Step 1: Write failing tests for parser and Func key fallback**

Add tests:

```python
class HardwarePanelCliTest(unittest.TestCase):
    def test_build_parser_defaults_to_key_enabled_and_oled_disabled(self):
        args = vim4_hw_panel.build_parser().parse_args([])

        self.assertFalse(args.no_key)
        self.assertFalse(args.oled)
        self.assertEqual(args.i2c_bus, 5)
        self.assertEqual(args.oled_addr, 0x3C)

    def test_func_key_status_missing_does_not_raise(self):
        with tempfile.TemporaryDirectory() as tmp:
            status = vim4_hw_panel.func_key_status(device=Path(tmp) / "event2")

        self.assertEqual(status.state, "missing")
        self.assertIn("adc_keypad", status.detail)

    def test_render_main_menu_contains_all_pages(self):
        menu = vim4_hw_panel.render_main_menu()

        self.assertIn("[1] Board Status", menu)
        self.assertIn("[8] Func Key Status", menu)
        self.assertIn("[q] Quit", menu)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_vim4_hw_panel.HardwarePanelCliTest -v`

Expected: FAIL with missing parser/menu/Func key helpers.

- [ ] **Step 3: Implement Func key and menu shell**

Add constants/functions:

```python
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


def func_key_status(device: Path = FUNC_KEY_DEVICE) -> StatusItem:
    if not device.exists():
        return StatusItem("Func key", "missing", f"missing {device}; expected {FUNC_KEY_NAME}")
    try:
        fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
    except PermissionError:
        return StatusItem("Func key", "permission denied", f"permission denied reading {device}; try sudo or add the user to the input group")
    except OSError as exc:
        return StatusItem("Func key", "missing", f"cannot open {device}: {exc}; expected {FUNC_KEY_NAME}")
    try:
        name = input_device_name(fd)
    except OSError as exc:
        return StatusItem("Func key", "missing", f"cannot read input name from {device}: {exc}; expected {FUNC_KEY_NAME}")
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive Khadas VIM4 hardware panel.")
    parser.add_argument("--no-key", action="store_true", help="disable optional Func key polling")
    parser.add_argument("--oled", action="store_true", help="enable optional SSD1306 OLED status output")
    parser.add_argument("--i2c-bus", type=int, default=5, help="OLED I2C bus, default: 5")
    parser.add_argument("--oled-addr", type=lambda value: int(value, 0), default=0x3C, help="OLED I2C address, default: 0x3c")
    return parser
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_vim4_hw_panel.HardwarePanelCliTest -v`

Expected: PASS.

### Task 5: Interactive Loop and Optional OLED

**Files:**
- Modify: `tests/test_vim4_hw_panel.py`
- Modify: `skills/vim4/hardware-control/scripts/vim4_hw_panel.py`

- [ ] **Step 1: Write failing tests for page dispatch and OLED fallback**

Add tests:

```python
class HardwarePanelDispatchTest(unittest.TestCase):
    def test_render_page_dispatches_known_page(self):
        text = vim4_hw_panel.render_page("5")

        self.assertIn("GPIO/PWM Map", text)

    def test_render_page_rejects_unknown_page(self):
        self.assertIn("Unknown", vim4_hw_panel.render_page("x"))

    def test_oled_summary_text_is_compact(self):
        text = vim4_hw_panel.oled_summary_text(cpu_percent=12.3, memory_percent=45.6, adc6="100", adc3="200")

        self.assertIn("CPU 12%", text)
        self.assertIn("MEM 46%", text)
        self.assertLessEqual(len(text.splitlines()), 4)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_vim4_hw_panel.HardwarePanelDispatchTest -v`

Expected: FAIL with missing dispatch/OLED helpers.

- [ ] **Step 3: Implement page dispatch, interactive loop, and OLED helpers**

Add:

```python
def render_led_control() -> str:
    try:
        brightness, max_brightness = led_values()
        return f"LED Control\n\nbrightness={brightness}\nmax_brightness={max_brightness}\n\nEnter a value from 0..{max_brightness}, or b to go back."
    except Exception as exc:
        return f"LED Control\n\n{exc}"


def render_fan_control() -> str:
    return "Fan Control\n\nActions: auto off low mid high temp mode\nEnter an action, or b to go back."


def oled_summary_text(cpu_percent: float, memory_percent: float, adc6: str, adc3: str) -> str:
    return "\n".join([
        f"CPU {cpu_percent:.0f}%",
        f"MEM {memory_percent:.0f}%",
        f"ADC6 {adc6}",
        f"ADC3 {adc3}",
    ])


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


def run_interactive(_args: argparse.Namespace) -> int:
    while True:
        clear_screen()
        print(render_main_menu())
        selection = prompt_input("> ")
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_interactive(args)
    except KeyboardInterrupt:
        print("")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_vim4_hw_panel.HardwarePanelDispatchTest -v`

Expected: PASS.

### Task 6: Full Verification and Commit

**Files:**
- Modify: `docs/superpowers/plans/2026-05-14-vim4-hardware-panel.md`
- Create: `tests/test_vim4_hw_panel.py`
- Create: `skills/vim4/hardware-control/scripts/vim4_hw_panel.py`

- [ ] **Step 1: Run full Python tests**

Run: `python3 -m unittest discover -v`

Expected: all tests pass.

- [ ] **Step 2: Run syntax check**

Run: `python3 -m py_compile skills/vim4/hardware-control/scripts/vim4_hw_panel.py tests/test_vim4_hw_panel.py`

Expected: exit code 0.

- [ ] **Step 3: Run CLI help**

Run: `python3 skills/vim4/hardware-control/scripts/vim4_hw_panel.py --help`

Expected: usage output includes `--no-key`, `--oled`, `--i2c-bus`, and `--oled-addr`.

- [ ] **Step 4: Review git diff**

Run: `git diff -- docs/superpowers/plans/2026-05-14-vim4-hardware-panel.md tests/test_vim4_hw_panel.py skills/vim4/hardware-control/scripts/vim4_hw_panel.py`

Expected: changes are limited to the implementation plan, new tests, and new script.

- [ ] **Step 5: Commit implementation**

```bash
git add docs/superpowers/plans/2026-05-14-vim4-hardware-panel.md tests/test_vim4_hw_panel.py skills/vim4/hardware-control/scripts/vim4_hw_panel.py
git commit -m "feat: add VIM4 hardware panel"
```

Expected: commit succeeds.

## Self-Review

- Spec coverage: all approved pages are covered by tasks 2-5; safety boundaries are covered by task 3 and read-only render tests; verification is covered by task 6.
- Placeholder scan: no TBD/TODO placeholders are used.
- Type consistency: shared names are `StatusItem`, `path_status`, `i2c_status`, `func_key_status`, `render_page`, and `build_parser` throughout the plan.
