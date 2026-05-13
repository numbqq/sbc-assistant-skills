# SBC Hardware Control Skills

AI assistant skills and helper scripts for Khadas single-board computer
hardware control and board-specific workflows.

This repository keeps Khadas SBC skills in Codex skill format and provides a
multi-agent installer that can copy the same skill bundle into the matching
skill directory for supported AI tools. Skills are organized by SBC product and
function area so the repository can grow across hardware control, NPU workflows,
system debugging, and future board-specific capabilities.

## Repository Layout

```text
scripts/
├── convert.sh
└── install.sh

skills/
└── vim4/
    └── hardware-control/
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

Future skill families should follow:

```text
skills/<product>/<domain>/
```

Examples:

```text
skills/vim4/npu/
skills/edge2/hardware-control/
skills/edge2/npu/
skills/common/linux-peripheral-io/
```

## Available Skills

### VIM4: `khadas-vim4-hardware-control`

Location:

```text
skills/vim4/hardware-control/
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

The installer discovers every `SKILL.md` under `skills/`. Choose a target with
`--tool`, choose one skill with `--skill` when needed, or install everything
with the defaults.

Convert generated integration formats:

```bash
./scripts/convert.sh
./scripts/convert.sh --tool openclaw
./scripts/convert.sh --tool claude-code --skill khadas-vim4-hardware-control
```

Show supported Agent/tool targets:

```bash
./scripts/install.sh --list-tools
```

Install all skills into Codex:

```bash
./scripts/install.sh
```

Install all skills into a specific target:

```bash
./scripts/install.sh --tool codex
./scripts/install.sh --tool claude-code
./scripts/install.sh --tool hermes
./scripts/convert.sh --tool openclaw
./scripts/install.sh --tool openclaw
```

Install to every supported target:

```bash
./scripts/convert.sh
./scripts/install.sh --tool all
```

Install a single skill:

```bash
./scripts/install.sh --tool codex --skill khadas-vim4-hardware-control
```

Preview source and target paths without copying files:

```bash
./scripts/install.sh --dry-run
./scripts/install.sh --tool all --dry-run
```

### Supported Targets

| Tool / Agent | Default install directory | Override environment variable |
| --- | --- | --- |
| Codex | `${CODEX_HOME:-$HOME/.codex}/skills/` | `CODEX_HOME` |
| Claude Code | `$HOME/.claude/agents/` | `CLAUDE_AGENTS_DIR` |
| Hermes | `$HOME/.hermes/skills/` | `HERMES_SKILLS_DIR` |
| OpenClaw | `$HOME/.openclaw/agency-agents/` | `OPENCLAW_AGENTS_DIR` |

Codex and Hermes receive the full `SKILL.md` bundle directory. Claude Code
expects single Markdown subagent files, and OpenClaw expects an agent workspace.
Run `convert.sh` before installing those targets; it writes local generated
artifacts under the ignored `integrations/` directory.

For Codex, the default target path is:

```text
${CODEX_HOME:-$HOME/.codex}/skills/khadas-vim4-hardware-control/
```

Manual install is also supported:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -a skills/vim4/hardware-control "${CODEX_HOME:-$HOME/.codex}/skills/khadas-vim4-hardware-control"
```

After installation, restart the target AI tool if it is already running. In
Codex, reference the skill as:

```text
$khadas-vim4-hardware-control
```

To update an existing local installation, rerun:

```bash
./scripts/install.sh --tool codex
```

Manual update:

```bash
rm -rf "${CODEX_HOME:-$HOME/.codex}/skills/khadas-vim4-hardware-control"
cp -a skills/vim4/hardware-control "${CODEX_HOME:-$HOME/.codex}/skills/khadas-vim4-hardware-control"
```

## Quick Usage

From the VIM4 skill directory:

```bash
cd skills/vim4/hardware-control
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
skills/vim4/hardware-control/references/vim4-minimal-hardware.md
```
