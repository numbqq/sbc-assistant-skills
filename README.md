# SBC Hardware Control Skills

AI assistant skills and helper scripts for single-board computer hardware
control.

This repository is organized by assistant platform. It currently provides Codex
skills, and Claude Code skills are planned for future additions. The first
available skill targets Khadas VIM4 on Ubuntu 24.04 and helps generate, review,
and debug small Bash or Python scripts for board peripherals.

## Repository Layout

```text
scripts/
└── install.sh

codex/
└── vim4-hardware-control-skills/
    ├── SKILL.md
    ├── agents/
    │   └── openai.yaml
    ├── references/
    │   └── vim4-minimal-hardware.md
    └── scripts/
        ├── adc_read.py
        ├── fan_control_demo.sh
        ├── i2c_read_write.py
        ├── oled_ssd1306_demo.py
        ├── oled_sys_monitor.py
        ├── spi_transfer.py
        ├── uart_comm.py
        ├── uart_read_write.py
        └── vim4_hw_minimal.sh
```

Future platform directories may include:

```text
claude-code/
```

## Available Skills

### Codex: `vim4-hardware-control`

Location:

```text
codex/vim4-hardware-control-skills/
```

Supported VIM4 hardware areas:

- LED via `/sys/class/leds/pwmled`
- Fan via `/usr/local/bin/fan.sh`
- ADC via Linux IIO raw nodes
- GPIO via wiringpi
- PWM via wiringpi
- I2C via Linux `/dev/i2c-*`
- SPI0 via Linux `/dev/spidev1.0`
- SSD1306 OLED over I2C
- UART_E via Linux `/dev/ttyS4`

The skill keeps examples minimal and favors read-only discovery checks before
commands that write hardware state.

## Installation

### Codex

Install the VIM4 skill into your Codex skills directory with one command:

```bash
./scripts/install.sh
```

Or specify the target tool explicitly:

```bash
./scripts/install.sh --tool codex
```

Preview the source and target paths without copying files:

```bash
./scripts/install.sh --dry-run
```

The installer copies:

```text
codex/vim4-hardware-control-skills/
```

to:

```text
${CODEX_HOME:-$HOME/.codex}/skills/vim4-hardware-control-skills/
```

Manual install is also supported:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -a codex/vim4-hardware-control-skills "${CODEX_HOME:-$HOME/.codex}/skills/"
```

After installation, restart Codex if it is already running, then reference the
skill as:

```text
$vim4-hardware-control
```

To update an existing local installation, rerun:

```bash
./scripts/install.sh --tool codex
```

Manual update:

```bash
rm -rf "${CODEX_HOME:-$HOME/.codex}/skills/vim4-hardware-control-skills"
cp -a codex/vim4-hardware-control-skills "${CODEX_HOME:-$HOME/.codex}/skills/"
```

### Claude Code

Claude Code skills are not included yet. When they are added, install
instructions will be documented under the corresponding `claude-code/` skill
directory.

## Quick Usage

From the VIM4 skill directory:

```bash
cd codex/vim4-hardware-control-skills
scripts/vim4_hw_minimal.sh gpio map
scripts/vim4_hw_minimal.sh adc status
scripts/vim4_hw_minimal.sh i2c status 5
scripts/vim4_hw_minimal.sh spi status
scripts/vim4_hw_minimal.sh uart status
```

Example helper commands:

```bash
python3 scripts/adc_read.py read 6
python3 scripts/adc_read.py watch 3 --interval 1 --count 5
sudo python3 scripts/i2c_read_write.py read --bus 5 --addr 0x40 --reg 0x00
sudo python3 scripts/oled_ssd1306_demo.py --bus 5 --addr 0x3c
sudo python3 scripts/spi_transfer.py transfer --device /dev/spidev1.0 --data 0x9f 0x00 0x00 0x00
sudo python3 scripts/uart_read_write.py send --device /dev/ttyS4 --baud 115200 --text "hello"
```

ADC raw reads:

```bash
scripts/vim4_hw_minimal.sh adc read 6
scripts/vim4_hw_minimal.sh adc read 3
python3 scripts/adc_read.py status
```

## Hardware Notes

- Confirm live board state before writing to GPIO, PWM, I2C, UART, LED, or fan
  controls.
- PIN10 is ADC_CH6 at `/sys/bus/iio/devices/iio:device0/in_voltage6_raw`;
  PIN12 is ADC_CH3 at `/sys/bus/iio/devices/iio:device0/in_voltage3_raw`.
- ADC input voltage range is 0 to 1.8V.
- Use wiringpi pin numbers for `gpio` commands unless a script explicitly says
  otherwise.
- Check `/dev/i2c-*` nodes before I2C access.
- Check `/dev/spidev1.0` before SPI0 access.
- Check `/dev/ttyS4` before UART_E access.
- VIM4 40-pin I2C, SPI, and UART overlays require a reboot before the runtime device
  nodes appear.
- SPI0 uses PIN25/PIN26/PIN36/PIN37 after the `spi0` overlay is active, and
  shares PIN25/PIN26 with I2C0.
- UART wiring should use 3.3V TTL levels, cross-connected TX/RX, and common GND.

## Reference

See the detailed VIM4 notes in:

```text
codex/vim4-hardware-control-skills/references/vim4-minimal-hardware.md
```
