# VIM4 Hardware Panel Design

## Goal

Build a comprehensive interactive terminal panel for the current
`khadas-vim4-hardware-control` skill. The application should make VIM4 hardware
status easy to inspect from one place, while keeping hardware writes limited and
explicit.

The first implementation target is a Python standard-library script:

```bash
skills/vim4/hardware-control/scripts/vim4_hw_panel.py
```

## Target Environment

- Board: Khadas VIM4
- OS: Ubuntu 24.04
- Runtime: Python 3 standard library
- Hardware conventions:
  - LED: `/sys/class/leds/pwmled`
  - Fan: `/usr/local/bin/fan.sh`
  - ADC: `/sys/bus/iio/devices/iio:device0/in_voltage6_raw` and
    `/sys/bus/iio/devices/iio:device0/in_voltage3_raw`
  - I2C: `/dev/i2c-5` and `/dev/i2c-0`
  - SPI0: `/dev/spidev1.0`
  - UART_E: `/dev/ttyS4`
  - Func key: `/dev/input/event2`, expected device name `adc_keypad`
  - GPIO/PWM: wiringpi pin numbering, read-only display in this application

## User Interface

The panel is a keyboard-first terminal menu. It must continue to work when the
Func key is unavailable, unreadable, or not the expected `adc_keypad` input
device.

Default commands:

```bash
python3 skills/vim4/hardware-control/scripts/vim4_hw_panel.py
python3 skills/vim4/hardware-control/scripts/vim4_hw_panel.py --no-key
python3 skills/vim4/hardware-control/scripts/vim4_hw_panel.py --oled --i2c-bus 5 --oled-addr 0x3c
```

Main menu:

```text
VIM4 Hardware Panel

[1] Board Status
[2] ADC Monitor
[3] LED Control
[4] Fan Control
[5] GPIO/PWM Map
[6] I2C/SPI/UART Status
[7] OLED Status Display
[8] Func Key Status
[q] Quit
```

Keyboard behavior:

- Number keys open pages.
- `r` refreshes the current page.
- `b` returns to the main menu.
- `q` exits.

Func key behavior:

- If `/dev/input/event2` is readable and its name is `adc_keypad`, the panel
  enables auxiliary input.
- Short press refreshes the current page or advances through simple panel states.
- The keyboard remains the primary and complete control path.
- If permission is denied, the panel reports that `sudo` or Linux `input` group
  membership may be needed.

## Pages

### Board Status

Shows readiness for:

- LED sysfs path
- Fan helper script
- ADC IIO raw nodes
- I2C0 and I2C5 device nodes
- SPI0 device node
- UART_E device node
- Func key input device

This page is read-only. Each item reports `ready`, `missing`, or `permission
denied` where applicable.

### ADC Monitor

Reads:

- PIN10 / ADC_CH6 from `in_voltage6_raw`
- PIN12 / ADC_CH3 from `in_voltage3_raw`

The page displays raw readings and may show an estimated voltage using a
configurable 12-bit, 1.8V default. The output must make clear that voltage is an
estimate unless the board image's ADC scale is confirmed.

### LED Control

Shows current `brightness` and `max_brightness`.

Allowed write operation:

- Set LED brightness after validating that the requested value is an integer in
  `0..max_brightness`.

Write errors should mention permission requirements.

### Fan Control

Uses only:

```bash
/usr/local/bin/fan.sh
```

Supported actions:

- `auto`
- `off`
- `low`
- `mid`
- `high`
- `temp`
- `mode`

The panel must not write MCU registers or attempt direct GPIO/PWM fan control.

### GPIO/PWM Map

Displays the VIM4 40-pin GPIO/PWM guidance from the existing skill:

- Use wiringpi `wPi` numbering with `gpio mode/read/write/pwm`.
- ADC-only pins are not digital GPIO outputs.
- I2C/SPI/UART-capable pins are GPIO only until their overlays are active.
- SPI0 shares PIN25/PIN26 with I2C0.

This page is read-only. It must not provide arbitrary GPIO or PWM write prompts.

### I2C/SPI/UART Status

Checks runtime device nodes:

- I2C5: `/dev/i2c-5`, requires `i2cm_f`
- I2C0: `/dev/i2c-0`, requires `i2cm_a`
- SPI0: `/dev/spidev1.0`, requires `spi0`
- UART_E: `/dev/ttyS4`, requires `uart_e`

Missing nodes should explain that the matching overlay must be enabled and the
system rebooted. This page is read-only and must not perform arbitrary bus
transfers.

### OLED Status Display

Optional mode enabled by `--oled`.

When available, the panel writes a concise system summary to an SSD1306 display:

- CPU usage
- Memory usage
- Fan temperature or mode when available
- ADC raw values when available

If the OLED or I2C bus is unavailable, the panel reports the problem and keeps
the terminal panel usable.

### Func Key Status

Reports:

- Device path
- Expected device name
- Actual device name when readable
- Availability and permission status

This page is read-only.

## Safety Boundaries

Default operation favors discovery and read-only checks.

Allowed writes:

- LED brightness via `/sys/class/leds/pwmled/brightness`
- Fan mode/query actions through `/usr/local/bin/fan.sh`
- Optional OLED display writes when `--oled` is explicitly enabled

Disallowed in this application:

- Arbitrary GPIO writes
- Arbitrary PWM writes
- Arbitrary I2C register writes
- Arbitrary SPI transfers
- Arbitrary UART send/receive operations
- Treating ADC pins as digital outputs
- Treating the Func key as GPIO/PWM/raw ADC
- Direct MCU fan control

## Error Handling

The panel should degrade cleanly on non-VIM4 systems or incomplete VIM4 setups.

Expected messages should be direct and actionable:

- `missing /dev/i2c-5; enable i2cm_f and reboot`
- `missing /dev/spidev1.0; enable spi0 and reboot`
- `permission denied reading /dev/input/event2; try sudo or add the user to the input group`
- `permission denied writing LED brightness; try sudo`

Unhandled tracebacks should be avoided for normal hardware absence or permission
errors.

## Implementation Notes

- Use only the Python standard library.
- Keep the script self-contained rather than importing current demo scripts with
  command-line side effects.
- Reuse the current skill's paths, pin mapping, and overlay guidance.
- Keep functions small and page-specific.
- The terminal UI can be simple text refreshes rather than a full-screen curses
  interface.
- OLED support can reuse the current SSD1306 command/data approach.

## Verification

Minimum verification:

```bash
python3 -m py_compile skills/vim4/hardware-control/scripts/vim4_hw_panel.py
python3 skills/vim4/hardware-control/scripts/vim4_hw_panel.py --help
```

Expected non-VIM4 behavior:

- The script starts.
- Missing hardware is reported as unavailable.
- The main menu remains usable.
- No hardware writes occur unless the LED, fan, or OLED paths are explicitly
  selected.

Hardware verification on VIM4, when available:

- Board Status reports detected nodes accurately.
- LED brightness writes respect `max_brightness`.
- Fan actions call `/usr/local/bin/fan.sh`.
- Func key availability is reported correctly.
- Optional OLED output does not block terminal use when unavailable.
