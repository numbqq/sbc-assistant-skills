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
├── vim4/
│   └── hardware-control/
│       ├── SKILL.md
│       ├── agents/
│       │   └── openai.yaml
│       ├── references/
│       │   └── vim4-minimal-hardware.md
│       └── scripts/
│           └── vim4_hw_minimal.sh
└── vim-5/
    ├── hardware-control/
    │   ├── SKILL.md
    │   ├── agents/
    │   │   └── openai.yaml
    │   ├── references/
    │   │   └── vim-5-minimal-hardware.md
    │   └── scripts/
    │       └── vim-5_hw_minimal.sh
    └── npu/
        ├── SKILL.md
        ├── agents/
        │   └── openai.yaml
        ├── references/
        │   └── vim-5-npu-yolov8n.md
        ├── scripts/
        │   ├── vim-5_npu_status.py
        │   ├── vim_5_yolov8n_core.py
        │   ├── vim-5_yolov8n_image.py
        │   └── vim-5_yolov8n_usb_camera.py
        └── assets/
            └── yolov8n/
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
skills/vim-5/hardware-control/
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

### Khadas VIM 5 Hardware Control

Skill name:

```text
khadas-vim-5-hardware-control
```

Location:

```text
skills/vim-5/hardware-control/
```

Coverage:

- LED via `/sys/class/leds/pwmled`
- Fan via `/usr/local/bin/fan.sh`
- ADC0/ADC1 via Linux IIO input nodes or wiringpi `gpio aread`
- GPIO via wiringpi
- PWM on PIN35 after the `pwm_j` overlay is active
- I2C3 on PIN22/PIN23 after `i2c_d`, and I2C6 on PIN25/PIN26 after `i2c_g`
- SPI1 on PIN25/PIN26/PIN36/PIN37 after `spi1`, using `/dev/spidev1.0`
- SSD1306 OLED over I2C
- UART on PIN15/PIN16 after `uart_ao_e`, using `/dev/ttyS4`
- SPDIF on PIN13 after `spdifout`
- IR on PIN39 after `ir`
- Func key via Linux input device `/dev/input/event3` named `adc_keypad`

### Khadas VIM 5 NPU

Skill name:

```text
khadas-vim-5-npu
```

Location:

```text
skills/vim-5/npu/
```

Coverage:

- VIM 5 integrated 8 TOPS NPU application workflows
- Dedicated conda Python environment `amlnnlite_py310`
- Common miniforge, miniconda, and anaconda conda executable auto-discovery
- Bundled YOLOv8n `.adla` inference model and sample image
- AMLNNLite runtime dependency checks for `amlnnlite`, `cv2`, and `numpy`
- Bundled YOLOv8n ADLA image inference script
- YOLOv8n USB camera inference with `/dev/video*` discovery
- No hard-coded external reference-code paths

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
./scripts/install.sh --tool codex --skill khadas-vim-5-hardware-control
./scripts/install.sh --tool codex --skill skills/vim-5/hardware-control
./scripts/install.sh --tool codex --skill khadas-vim-5-npu
./scripts/install.sh --tool codex --skill skills/vim-5/npu
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

Activation examples:

```text
codex=$khadas-vim4-hardware-control
codex=$khadas-vim-5-hardware-control
claude-code=restart Claude Code, then use /khadas-vim4-hardware-control
claude-code=restart Claude Code, then use /khadas-vim-5-hardware-control
gemini-cli=restart Gemini CLI, then run /skills reload and /skills list
hermes=restart Hermes, then use the khadas-vim4-hardware-control skill
hermes=restart Hermes, then use the khadas-vim-5-hardware-control skill
openclaw=restart OpenClaw gateway, then use the khadas-vim4-hardware-control agent
openclaw=restart OpenClaw gateway, then use the khadas-vim-5-hardware-control agent
```

## Updating Installed Skills

When a new version of this repository is released, update the installed skills
by updating your local copy of this repository first, then running the same
install command again. The installer replaces the target skill directory, so
reinstalling the same skill is the supported update path.

If you installed from a git checkout:

```bash
cd sbc-assistant-skills
git pull
./scripts/install.sh --tool codex --skill khadas-vim-5-hardware-control
```

If you installed from a downloaded release archive, download and extract the new
release, then run the installer from the extracted repository:

```bash
cd sbc-assistant-skills
./scripts/install.sh --tool codex --skill khadas-vim-5-hardware-control
```

Update all installed skills for one target:

```bash
./scripts/install.sh --tool codex
./scripts/install.sh --tool claude-code
./scripts/install.sh --tool gemini-cli
./scripts/install.sh --tool hermes
```

Update all supported targets:

```bash
./scripts/convert.sh
./scripts/install.sh --tool all
```

For OpenClaw, regenerate the converted agent workspace before installing:

```bash
./scripts/convert.sh --tool openclaw --skill khadas-vim-5-hardware-control
./scripts/install.sh --tool openclaw --skill khadas-vim-5-hardware-control
```

For Gemini CLI extension artifacts under `integrations/`, regenerate before
packaging or installing the converted extension:

```bash
./scripts/convert.sh --tool gemini-cli --skill khadas-vim-5-hardware-control
./scripts/install.sh --tool gemini-cli --skill khadas-vim-5-hardware-control
```

After updating, restart the target AI tool if it is already running. For Gemini
CLI, also run `/skills reload` and `/skills list` after restart if needed.

## Uninstalling Skills

There is no separate uninstall command. Remove the installed skill directory
from the target tool's skills directory.

Codex example:

```bash
rm -rf "${CODEX_HOME:-$HOME/.codex}/skills/khadas-vim-5-hardware-control"
```

Other default install locations:

```bash
rm -rf "$HOME/.claude/skills/khadas-vim-5-hardware-control"
rm -rf "$HOME/.gemini/skills/khadas-vim-5-hardware-control"
rm -rf "$HOME/.hermes/skills/khadas-vim-5-hardware-control"
rm -rf "$HOME/.openclaw/agency-agents/khadas-vim-5-hardware-control"
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

## VIM 5 Quick Usage

From the VIM 5 hardware-control skill directory:

```bash
cd skills/vim-5/hardware-control
scripts/vim-5_hw_minimal.sh gpio map
scripts/vim-5_hw_minimal.sh adc status
scripts/vim-5_hw_minimal.sh i2c status 3
scripts/vim-5_hw_minimal.sh i2c status 6
scripts/vim-5_hw_minimal.sh spi status
scripts/vim-5_hw_minimal.sh uart status
scripts/vim-5_hw_minimal.sh pwm status
```

Example helper commands:

```bash
python3 scripts/adc_read.py read 0
python3 scripts/adc_read.py aread 0
python3 scripts/adc_read.py watch 1 --interval 1 --count 5
scripts/vim-5_hw_minimal.sh adc aread 0
scripts/vim-5_hw_minimal.sh adc aread 1
gpio aread 19
gpio aread 20
cat /sys/bus/iio/devices/iio:device0/in_voltage0_input
cat /sys/bus/iio/devices/iio:device0/in_voltage3_input
sudo python3 scripts/i2c_read_write.py read --bus 3 --addr 0x40 --reg 0x00
sudo python3 scripts/oled_ssd1306_demo.py --bus 3 --addr 0x3c
sudo python3 scripts/spi_transfer.py transfer --device /dev/spidev1.0 --data 0x9f 0x00 0x00 0x00
sudo python3 scripts/uart_read_write.py send --device /dev/ttyS4 --baud 115200 --text "hello"
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

Current VIM 5 notes:

- PIN10 is ADC0 at `/sys/bus/iio/devices/iio:device0/in_voltage0_input`
  or wiringpi `gpio aread 19`; PIN12 is ADC1 at
  `/sys/bus/iio/devices/iio:device0/in_voltage3_input` or wiringpi
  `gpio aread 20`.
- Check `/dev/i2c-3` for PIN22/PIN23 after `i2c_d`; check `/dev/i2c-6`
  for PIN25/PIN26 after `i2c_g`.
- SPI1 uses PIN25/PIN26/PIN36/PIN37 after `spi1`, exposes
  `/dev/spidev1.0`, and shares PIN25/PIN26 with I2C6.
- UART uses PIN15/PIN16 after `uart_ao_e` and exposes `/dev/ttyS4`.
- PIN13 SPDIF needs `spdifout`, PIN35 PWM needs `pwm_j`, and PIN39 IR needs
  `ir`; all are GPIO by default.
- Func key uses Linux input device `/dev/input/event3` named `adc_keypad`.

## Reference

Detailed VIM4 and VIM 5 notes:

```text
skills/vim4/hardware-control/references/vim4-minimal-hardware.md
skills/vim-5/hardware-control/references/vim-5-minimal-hardware.md
```
