# SBC Assistant Skills

AI assistant skills and helper scripts for single-board computer hardware,
accelerators, system debugging, and board-specific workflows.

This repository is a reusable skill registry. Skills are stored once in Codex
skill format under `skills/`, then converted or installed into the matching
layout for supported AI tools. The structure is intentionally organized by SBC
product and function area so new boards and new skill families can be added
without changing installer behavior.

## Repository Layout

```text
scripts/
├── convert.sh
└── install.sh

skills/
└── <product>/
    └── <domain>/
        ├── SKILL.md
        ├── agents/
        │   └── openai.yaml
        ├── references/
        │   └── ...
        └── scripts/
            └── ...
```

Current example:

```text
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
            ├── key_input.py
            ├── oled_ssd1306_demo.py
            ├── oled_sys_monitor.py
            ├── spi_transfer.py
            ├── uart_comm.py
            ├── uart_read_write.py
            └── vim4_hw_minimal.sh
```

## Skill Naming

Each installable skill is any directory below `skills/` that contains
`SKILL.md`. The installer discovers these files automatically.

Use this directory pattern for board-specific skills:

```text
skills/<product>/<domain>/
```

Use `skills/common/<domain>/` for cross-board skills that are not tied to one
SBC product.

Examples:

```text
skills/vim4/hardware-control/
skills/vim4/npu/
skills/edge2/hardware-control/
skills/edge2/npu/
skills/common/linux-peripheral-io/
skills/common/system-debug/
```

The `name:` field in `SKILL.md` is the public skill or agent name used by
installers and generated integrations. Prefer stable names that include the
vendor or board when the skill is board-specific, for example:

```yaml
name: khadas-vim4-hardware-control
```

## Available Skills

### Khadas VIM4 Hardware Control

Skill name:

```text
khadas-vim4-hardware-control
```

Location:

```text
skills/vim4/hardware-control/
```

Coverage:

- LED via `/sys/class/leds/pwmled`
- Fan via `/usr/local/bin/fan.sh`
- ADC via Linux IIO raw nodes
- GPIO via wiringpi
- PWM via wiringpi
- I2C via Linux `/dev/i2c-*`
- SPI0 via Linux `/dev/spidev1.0`
- SSD1306 OLED over I2C
- UART_E via Linux `/dev/ttyS4`
- Func key via Linux input device `/dev/input/event2` named `adc_keypad`

The skill keeps examples minimal and favors read-only discovery checks before
commands that write hardware state.

## Installation

The installer discovers every `SKILL.md` under `skills/`. Choose a target with
`--tool`, choose one skill with `--skill` when needed, or install everything
with the defaults.

Show supported targets:

```bash
./scripts/install.sh --list-tools
./scripts/convert.sh --list-tools
```

Convert generated integration formats:

```bash
./scripts/convert.sh
./scripts/convert.sh --tool gemini-cli
./scripts/convert.sh --tool openclaw
```

Codex, Claude Code, and Hermes use the native skill bundle directly, so
conversion is a no-op for those targets. Use `install.sh` to install them.

Install all skills into the default target, Codex:

```bash
./scripts/install.sh
```

Install all skills into a specific target:

```bash
./scripts/install.sh --tool codex
./scripts/install.sh --tool claude-code
./scripts/install.sh --tool gemini-cli
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
./scripts/install.sh --tool codex --skill skills/vim4/hardware-control
```

Preview source and target paths without copying files:

```bash
./scripts/install.sh --dry-run
./scripts/install.sh --tool all --dry-run
```

### Supported Targets

| Tool / Agent | Default install directory | Override environment variable | Conversion |
| --- | --- | --- | --- |
| Codex | `${CODEX_HOME:-$HOME/.codex}/skills/` | `CODEX_HOME` | Native skill bundle |
| Claude Code | `$HOME/.claude/skills/` | `CLAUDE_SKILLS_DIR` | Native skill bundle |
| Gemini CLI | `$HOME/.gemini/skills/` | `GEMINI_SKILLS_DIR` | Native skill bundle |
| Hermes | `$HOME/.hermes/skills/` | `HERMES_SKILLS_DIR` | Native skill bundle |
| OpenClaw | `$HOME/.openclaw/agency-agents/` | `OPENCLAW_AGENTS_DIR` | Agent workspace |

Generated integration artifacts are written under the ignored
`integrations/` directory:

```text
integrations/
├── gemini-cli/extensions/<skill-name>/
└── openclaw/agents/<skill-name>/
```

Codex, Claude Code, Gemini CLI, and Hermes receive the full source skill
directory. OpenClaw receives an agent workspace. `convert.sh --tool gemini-cli`
is still available when you want a Gemini CLI extension artifact; the generated
extension bundles the skill under `skills/<skill-name>/`.

Claude Code and Gemini CLI also support project-level skills. Use `--local` to
install into this repository's `.claude/skills/` and `.gemini/skills/`
directories:

```bash
./scripts/install.sh --tool claude-code --local
./scripts/install.sh --tool gemini-cli --local
```

After installation, restart the target AI tool if it is already running.

Activation examples for the current VIM4 skill:

```text
codex=$khadas-vim4-hardware-control
claude-code=restart Claude Code, then use /khadas-vim4-hardware-control
gemini-cli=restart Gemini CLI, then run /skills reload and /skills list
hermes=restart Hermes, then use the khadas-vim4-hardware-control skill
openclaw=restart OpenClaw gateway, then use the khadas-vim4-hardware-control agent
```

## Adding Skills

To add support for another SBC or feature area:

1. Create a new directory under `skills/<product>/<domain>/` or
   `skills/common/<domain>/`.
2. Add `SKILL.md` with frontmatter that includes at least `name:` and
   `description:`.
3. Put reusable scripts under `scripts/` and long-form board notes under
   `references/`.
4. Keep board-specific assumptions inside that skill instead of hardcoding them
   in `scripts/install.sh` or `scripts/convert.sh`.
5. Run `./scripts/convert.sh` and `./scripts/install.sh --dry-run` to verify
   discovery, generated names, and target paths.

Minimal structure:

```text
skills/<product>/<domain>/
├── SKILL.md
├── references/
└── scripts/
```

`SKILL.md` frontmatter example:

```yaml
---
name: vendor-board-domain
description: concise trigger description for this board or feature skill
---
```

## VIM4 Quick Usage

From the VIM4 hardware-control skill directory:

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

- Confirm live board state before writing to GPIO, PWM, I2C, UART, LED, fan,
  regulator, or accelerator controls.
- Keep voltage limits, pin mappings, overlay requirements, device nodes, and
  board-specific package assumptions in the matching skill documentation.
- Prefer read-only discovery commands before commands that mutate hardware or
  system state.
- Use `skills/common/` only for behavior that is genuinely shared across SBCs.

Current VIM4 notes:

- PIN10 is ADC_CH6 at `/sys/bus/iio/devices/iio:device0/in_voltage6_raw`;
  PIN12 is ADC_CH3 at `/sys/bus/iio/devices/iio:device0/in_voltage3_raw`.
- ADC input voltage range is 0 to 1.8V.
- Use wiringpi pin numbers for `gpio` commands unless a script explicitly says
  otherwise.
- Check `/dev/i2c-*` nodes before I2C access.
- Check `/dev/spidev1.0` before SPI0 access.
- Check `/dev/ttyS4` before UART_E access.
- VIM4 40-pin I2C, SPI, and UART overlays require a reboot before the runtime
  device nodes appear.
- SPI0 uses PIN25/PIN26/PIN36/PIN37 after the `spi0` overlay is active, and
  shares PIN25/PIN26 with I2C0.
- UART wiring should use 3.3V TTL levels, cross-connected TX/RX, and common GND.

## Reference

Detailed VIM4 notes:

```text
skills/vim4/hardware-control/references/vim4-minimal-hardware.md
```
