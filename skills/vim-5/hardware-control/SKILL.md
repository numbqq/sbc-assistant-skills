---
name: khadas-vim-5-hardware-control
description: minimal hardware control helper for Khadas VIM 5 running Ubuntu 24.04. use when asked to generate, review, or debug Python or Bash scripts for LED, ADC, GPIO, PWM, I2C, SPI, OLED/LCD, UART, Func key, fan, expansion-board green LED, analog MIC, Mic Array, or three-wire SPI display control on VIM 5. assumes fan control uses /usr/local/bin/fan.sh, board LED control uses /sys/class/leds/pwmled, expansion-board green LED uses /sys/class/leds/green_led, ADC uses /sys/bus/iio/devices/iio:device0/in_voltage*_input or wiringpi gpio aread 19/20, GPIO and PWM use wiringpi tools, I2C uses Linux /dev/i2c-* with Python ioctl helpers after checking /dev/i2c-3 or /dev/i2c-6 exists, SPI1 uses /dev/spidev1.0 after enabling the spi1 or spi1-lcd overlay, analog MIC uses ext-board-codec plus ALSA hw:0,1, Mic Array records from hw:0,3, UART uses /dev/ttyS4 after enabling the uart_ao_e overlay, and the board Func key uses /dev/input/event3 with device name adc_keypad.
---

# VIM 5 Hardware Control

## Scope

Use this skill to help generate and troubleshoot minimal hardware-control scripts for Khadas VIM 5 on Ubuntu 24.04.

Supported only:
- LED via `/sys/class/leds/pwmled`
- FAN via `/usr/local/bin/fan.sh`
- ADC via IIO sysfs input nodes under `/sys/bus/iio/devices/iio:device0` or wiringpi `gpio aread`
- GPIO via wiringpi
- PWM via wiringpi
- I2C via Linux `/dev/i2c-*` and Python `I2C_SLAVE` ioctl
- SPI1 via Linux `/dev/spidev1.0` and Python `SPI_IOC_MESSAGE` ioctl
- OLED over I2C via the bundled SSD1306 helper
- UART via Linux `/dev/ttyS4` and Python `termios`
- board Func key via Linux input device `/dev/input/event3` named `adc_keypad`
- VIM 5 expansion-board green LED via `/sys/class/leds/green_led`
- VIM 5 expansion-board analog MIC via `ext-board-codec`, ALSA route setup, and `arecord` on `hw:0,1`
- VIM 5 Mic Array recording via `arecord` on `hw:0,3`
- VIM 5 expansion-board three-wire SPI OLED/LCD via `spi1-lcd`, `/dev/spidev1.0`, and the bundled `scripts/spi_lcd_st7735.py` ST7735 helper

For VIM 5 40-pin I2C, SPI, or UART, check whether the matching device node exists. Do not treat overlay file contents as runtime status because `fdt_overlays` changes require reboot to take effect.

## Default assumptions

- Target board: Khadas VIM 5 SBC
- OS: Ubuntu 24.04
- Script languages: Python or Bash
- `wiringpi` is installed and available for GPIO/PWM on the target system
- ADC header inputs are read-only values with a 0 to 1.8V input range: PIN10 is ADC0 at `/sys/bus/iio/devices/iio:device0/in_voltage0_input` or `gpio aread 19`; PIN12 is ADC1 at `/sys/bus/iio/devices/iio:device0/in_voltage3_input` or `gpio aread 20`
- I2C access uses `/dev/i2c-<bus>` after the matching bus is exposed by the system
- 40-pin header PIN22/PIN23 are I2C3 when `i2c_d` has been enabled and the system has rebooted
- 40-pin header PIN25/PIN26 are I2C6 when `i2c_g` has been enabled and the system has rebooted
- 40-pin header PIN25/PIN26/PIN36/PIN37 are SPI1 when `spi1` has been enabled and the system has rebooted
- 40-pin header PIN15/PIN16 are UART when `uart_ao_e` has been enabled and the system has rebooted
- 40-pin header PIN35 is PWM when `pwm_j` has been enabled and the system has rebooted
- 40-pin header PIN13 is SPDIF when `spdifout` has been enabled and the system has rebooted
- 40-pin header PIN39 is IR when `ir` has been enabled and the system has rebooted
- I2C3, I2C6, SPI1, UART, PWM, SPDIF, and IR header pins behave as normal GPIO by default until their overlay is enabled and active
- SPI1 shares PIN25/PIN26 with I2C6; do not enable or use both functions on those pins at the same time
- Fan is controlled by MCU through `/usr/local/bin/fan.sh`
- LED sysfs node is `/sys/class/leds/pwmled`
- Board Func key is read-only through Linux input device `/dev/input/event3`, which should report device name `adc_keypad`
- Expansion-board green LED sysfs node is `/sys/class/leds/green_led`
- Expansion-board analog MIC requires the board to be attached and `fdt_overlays=ext-board-codec`; configure capture path with `amixer -c 0 cset name='TDMIN_B source select' 'tdmin_b'`, then record from `hw:0,1`
- Mic Array recording uses `arecord -Dhw:0,3 -r 48000 -f S16_LE -c 6`
- Expansion-board three-wire SPI OLED/LCD requires `fdt_overlays=spi1-lcd`, uses `/dev/spidev1.0`, and is controlled by bundled helper `scripts/spi_lcd_st7735.py`
- The `ext-board-codec` overlay shares pins with I2S and SPI functions; do not enable or use conflicting overlays at the same time

## Safety rules

Before generating commands that write hardware state:
1. Prefer discovery/read-only checks first.
2. Avoid hardcoding unknown pin numbers unless the user provided them.
3. Remind the user that GPIO/PWM pin numbering must match wiringpi numbering on the target board.
4. Use `sudo` only when needed for sysfs writes, wiringpi access, or `/dev/i2c-*` permissions.
5. For fan control, use `/usr/local/bin/fan.sh`; do not invent MCU register writes.
6. For ADC, read only the matching `in_voltage*_input` file or use wiringpi `gpio aread 19` for ADC0 and `gpio aread 20` for ADC1; do not treat ADC pins as digital GPIO outputs.
7. For I2C on bus 3 or bus 6, check `/dev/i2c-3` or `/dev/i2c-6` before I2C reads/writes.
8. For I2C writes, confirm the bus and address with read-only discovery first when possible.
9. For SPI1, check `/dev/spidev1.0` before SPI transfers.
10. For SPI writes/transfers, confirm SPI mode, speed, bits per word, chip-select wiring, and voltage level first when possible.
11. For UART, check `/dev/ttyS4` before serial reads/writes.
12. Remind users to cross-connect UART TX/RX, share GND, and use 3.3V TTL levels rather than RS-232 voltage levels.
13. For the board Func key, read only `/dev/input/event3`; do not treat it as a GPIO, PWM, or raw ADC input.
14. For expansion-board analog MIC, remind users that the expansion board must be connected and `ext-board-codec` must be active after reboot before ALSA capture from `hw:0,1` works.
15. For expansion-board SPI OLED/LCD, check `/dev/spidev1.0` before display transfers and use the bundled `scripts/spi_lcd_st7735.py` helper for ST7735-compatible panels.
16. Avoid combining `ext-board-codec`, `spi1-lcd`, I2S, or SPI overlays that claim the same shared pins unless the user provides a confirmed mux configuration.

## Workflow

1. Identify the requested hardware block: LED, FAN, ADC, GPIO, PWM, I2C, SPI, UART, Func key, or expansion-board device.
2. Generate the smallest working Bash or Python script.
3. Include a read/check command when possible.
4. Include short usage examples.
5. Avoid Device Tree, kernel overlay, or driver rebuild steps except a short VIM 5 40-pin I2C/SPI/UART note when the matching device node is missing.

## LED control

Use sysfs path:

```bash
/sys/class/leds/pwmled
```

Common files to check:

```bash
ls -l /sys/class/leds/pwmled
cat /sys/class/leds/pwmled/brightness
cat /sys/class/leds/pwmled/max_brightness
cat /sys/class/leds/pwmled/trigger
```

For simple on/off or brightness scripts, write to `brightness`. Use `max_brightness` to avoid invalid values.

For the expansion-board green LED, use:

```bash
/sys/class/leds/green_led
```

Useful checks and examples:

```bash
scripts/vim-5_hw_minimal.sh ext-board green-led status
scripts/vim-5_hw_minimal.sh ext-board green-led brightness 1
python3 scripts/led_blink.py --led-path /sys/class/leds/green_led --delay 0.1
```

## ADC through Linux IIO sysfs

Use IIO input files:

```bash
/sys/bus/iio/devices/iio:device0/in_voltage0_input
/sys/bus/iio/devices/iio:device0/in_voltage3_input
```

40-pin header ADC mapping:
- PIN10 is ADC0 at `/sys/bus/iio/devices/iio:device0/in_voltage0_input`; wiringpi ADC command is `gpio aread 19`
- PIN12 is ADC1 at `/sys/bus/iio/devices/iio:device0/in_voltage3_input`; wiringpi ADC command is `gpio aread 20`
- ADC input voltage range is 0 to 1.8V

Useful checks:

```bash
scripts/vim-5_hw_minimal.sh adc status
scripts/vim-5_hw_minimal.sh adc read 0
scripts/vim-5_hw_minimal.sh adc read 1
scripts/vim-5_hw_minimal.sh adc aread 0
scripts/vim-5_hw_minimal.sh adc aread 1
gpio aread 19
gpio aread 20
cat /sys/bus/iio/devices/iio:device0/in_voltage0_input
cat /sys/bus/iio/devices/iio:device0/in_voltage3_input
```

ADC input values are board/driver readings. Do not convert them again unless the target image's IIO units or scale are known.

## FAN control

Always use:

```bash
/usr/local/bin/fan.sh
```

Supported commands:

```bash
/usr/local/bin/fan.sh on
/usr/local/bin/fan.sh auto
/usr/local/bin/fan.sh off
/usr/local/bin/fan.sh low
/usr/local/bin/fan.sh mid
/usr/local/bin/fan.sh high
/usr/local/bin/fan.sh temp
/usr/local/bin/fan.sh trig
/usr/local/bin/fan.sh mode
/usr/local/bin/fan.sh -h
```

When asked to control the fan, generate wrappers around this script rather than direct GPIO/PWM control.

## GPIO through wiringpi

Prefer wiringpi commands for GPIO:

```bash
gpio readall
scripts/vim-5_hw_minimal.sh gpio map
gpio mode <pin> out
gpio write <pin> 1
gpio write <pin> 0
gpio mode <pin> in
gpio read <pin>
```

Use `<pin>` as wiringpi pin number unless the user states another numbering scheme.

For the default VIM 5 40-pin header state reported by `gpio readall`:
- Default digital GPIO inputs: physical PIN13/wPi1/GPIO641, PIN15/wPi2/GPIO637, PIN16/wPi3/GPIO636, PIN22/wPi6/GPIO591, PIN23/wPi7/GPIO590, PIN25/wPi8/GPIO555, PIN26/wPi9/GPIO554, PIN29/wPi10/GPIO577, PIN30/wPi11/GPIO576, PIN31/wPi12/GPIO579, PIN32/wPi13/GPIO578, PIN33/wPi14/GPIO580, PIN35/wPi15/GPIO601, PIN36/wPi16/GPIO556, PIN37/wPi17/GPIO557, and PIN39/wPi18/GPIO633.
- Alternate-function pins by default: physical PIN18/wPi4/GPIO629/PIN.D1 and PIN19/wPi5/GPIO628/PIN.D0. Do not use them as generic GPIO examples unless intentionally switching their mode.
- Analog entries physical PIN10/wPi19/ADC0 and PIN12/wPi20/ADC1 do not show Linux GPIO numbers in the default table; treat them as ADC channels, not digital GPIO write targets.
- Non-GPIO header pins include 5V, 3V3, GND, 1.8V, MCU3.3, USB_DM/USB_DP, MCUNRST, MCUSWIM, and PWR_HOLD.
- 40-pin I2C/SPI-capable pins are GPIO by default: PIN22/PIN23 are PIN.A15/PIN.A14 and become I2C3 only after `i2c_d` is active; PIN25/PIN26 are PIN.M1/PIN.M0 and become I2C6 only after `i2c_g` is active; PIN25/PIN26/PIN36/PIN37 become SPI1 only after `spi1` is active. SPI1 and I2C6 share PIN25/PIN26, so use only one of those functions at a time.
- 40-pin UART-capable pins are GPIO by default: PIN15/PIN16 are PIN.D9/PIN.D8 and become UART RX/TX only after `uart_ao_e` is active.
- Other 40-pin alternate functions are GPIO by default: PIN13 becomes SPDIF with `spdifout`, PIN35 becomes PWM with `pwm_j`, and PIN39 becomes IR with `ir`.

## PWM through wiringpi

On VIM 5, PIN35/wPi15/GPIO601 is GPIO by default and becomes PWM only after `pwm_j` is active and the system has rebooted. Use wiringpi PWM only when the selected pin supports PWM. Use conservative examples:

```bash
scripts/vim-5_hw_minimal.sh pwm status
gpio mode <pin> pwm
gpio pwm <pin> <value>
```

If range/clock settings are needed, expose them as parameters and warn that valid values depend on wiringpi support for the selected pin.

## I2C through Linux i2c-dev

For I2C tasks, do not use wiringpi. Use Linux `/dev/i2c-*` device nodes and Python helpers based on `fcntl.ioctl(fd, I2C_SLAVE, addr)`.

For 40-pin header I2C:
- PIN22/PIN23 are I2C3 and require `fdt_overlays=i2c_d`
- PIN25/PIN26 are I2C6 and require `fdt_overlays=i2c_g`
- The overlay config file is `/boot/dtb/amlogic/kvim-5.dtb.overlay.env`
- Overlay files live under `/boot/dtb/amlogic/kvim-5.dtb.overlays`
- `fdt_overlays` changes require reboot, so runtime readiness is determined by `/dev/i2c-3` or `/dev/i2c-6`
- If the node is missing, explain that I2C is not active on that header bus; the pins remain normal GPIO until the overlay is enabled and the system reboots

Useful checks:

```bash
scripts/vim-5_hw_minimal.sh i2c status 3
scripts/vim-5_hw_minimal.sh i2c status 6
i2cdetect -l
ls -l /dev/i2c-<bus>
i2cdetect -y <bus>
```

Bundled helpers:

```bash
scripts/i2c_read_write.py read --bus 3 --addr 0x40 --reg 0x00
scripts/i2c_read_write.py write --bus 3 --addr 0x40 --reg 0x01 --value 0xff
scripts/i2c_read_write.py write-bytes --bus 3 --addr 0x3c --data 0x00 0xae
scripts/oled_ssd1306_demo.py --bus 3 --addr 0x3c
```

Keep bus number, device address, register, and raw bytes configurable. Prefer no external Python dependency for I2C; use `smbus2` only if the user explicitly requests SMBus APIs.

## SPI through Linux spidev

For VIM 5 40-pin header SPI:
- PIN25/PIN26/PIN36/PIN37 are SPI1 and require `fdt_overlays=spi1`
- Device node is `/dev/spidev1.0`
- SPI1 shares PIN25/PIN26 with I2C6; do not use SPI1 and I2C6 on those pins at the same time
- The overlay config file is `/boot/dtb/amlogic/kvim-5.dtb.overlay.env`
- Overlay files live under `/boot/dtb/amlogic/kvim-5.dtb.overlays`
- `fdt_overlays` changes require reboot, so runtime readiness is determined by `/dev/spidev1.0`
- If the node is missing, explain that SPI1 is not active on PIN25/PIN26/PIN36/PIN37; enable `spi1` and reboot

Useful checks:

```bash
scripts/vim-5_hw_minimal.sh spi status
ls -l /dev/spidev1.0
```

Enable note:

```bash
# Edit /boot/dtb/amlogic/kvim-5.dtb.overlay.env so fdt_overlays includes spi1, then reboot.
fdt_overlays=spi1
```

Bundled helper:

```bash
scripts/spi_transfer.py transfer --device /dev/spidev1.0 --mode 0 --speed 500000 --data 0x9f 0x00 0x00 0x00
scripts/vim-5_hw_minimal.sh spi transfer 0x9f 0x00 0x00 0x00
```

Keep device path, mode, speed, bits per word, and byte payload configurable. Prefer the bundled stdlib ioctl helper; use `spidev` Python packages only if the user explicitly requests them.

## UART through Linux tty

For VIM 5 40-pin header UART:
- PIN15 is UART RX
- PIN16 is UART TX
- Device node is `/dev/ttyS4`
- Required overlay is `uart_ao_e`
- The overlay config file is `/boot/dtb/amlogic/kvim-5.dtb.overlay.env`
- Overlay files live under `/boot/dtb/amlogic/kvim-5.dtb.overlays`
- `fdt_overlays` changes require reboot, so runtime readiness is determined by `/dev/ttyS4`
- If the node is missing, explain that UART is not active on PIN15/PIN16; enable `uart_ao_e` and reboot

Useful checks:

```bash
scripts/vim-5_hw_minimal.sh uart status
ls -l /dev/ttyS4
```

Enable note:

```bash
# Edit /boot/dtb/amlogic/kvim-5.dtb.overlay.env so fdt_overlays includes uart_ao_e, then reboot.
fdt_overlays=uart_ao_e
```

Bundled helper:

```bash
scripts/uart_read_write.py send --device /dev/ttyS4 --baud 115200 --text "hello"
scripts/uart_read_write.py receive --device /dev/ttyS4 --baud 115200 --timeout 5
scripts/uart_read_write.py loopback --device /dev/ttyS4 --baud 115200 --text "hello"
```

Keep device path, baud rate, timeout, and payload configurable. Prefer the bundled stdlib `termios` helper; use `pyserial` only if the user explicitly requests it.

## Func key through Linux input

The VIM 5 board Func key is exposed by Linux input as:

```bash
/dev/input/event3
```

The expected device name is:

```text
adc_keypad
```

Useful checks:

```bash
scripts/vim-5_hw_minimal.sh key status
scripts/vim-5_hw_minimal.sh key wait 10
scripts/vim-5_hw_minimal.sh key listen
```

Bundled helper:

```bash
scripts/key_input.py status
scripts/key_input.py wait --timeout 10
scripts/key_input.py listen
```

Only support the board Func key for this skill. Keep examples read-only, use `/dev/input/event3`, and report press, release, or repeat events from EV_KEY input events. If reading the device returns permission denied, suggest `sudo` or membership in the Linux `input` group.

## VIM 5 expansion board

The VIM 5 expansion board adds a green LED, analog MIC, Mic Array, and a three-wire SPI OLED/LCD.

Green LED:

```bash
scripts/vim-5_hw_minimal.sh ext-board green-led status
scripts/vim-5_hw_minimal.sh ext-board green-led brightness 1
python3 scripts/led_blink.py --led-path /sys/class/leds/green_led --delay 0.1
```

Analog MIC:

```bash
scripts/vim-5_hw_minimal.sh ext-board analog-mic status
scripts/vim-5_hw_minimal.sh ext-board analog-mic configure
scripts/vim-5_hw_minimal.sh ext-board analog-mic record 10 test.wav
```

Analog MIC requires the expansion board and `fdt_overlays=ext-board-codec`. The exact route setup is `amixer -c 0 cset name='TDMIN_B source select' 'tdmin_b'`; the exact capture command is `arecord -D hw:0,1 -f cd -c 2 -d 10 test.wav`.

Mic Array:

```bash
scripts/vim-5_hw_minimal.sh ext-board mic-array status
scripts/vim-5_hw_minimal.sh ext-board mic-array record 10 pdm_6ch.wav
```

The exact Mic Array capture command is `arecord -Dhw:0,3 -r 48000 -f S16_LE -c 6 -d 10 pdm_6ch.wav`.

Three-wire SPI OLED/LCD:

```bash
scripts/vim-5_hw_minimal.sh ext-board spi-lcd status
scripts/vim-5_hw_minimal.sh ext-board spi-lcd test
scripts/vim-5_hw_minimal.sh ext-board spi-lcd clear black
scripts/vim-5_hw_minimal.sh ext-board spi-lcd text "Khadas" "VIM 5"
```

The display requires `fdt_overlays=spi1-lcd`, uses `/dev/spidev1.0`, and uses the bundled `scripts/spi_lcd_st7735.py` helper. Install dependencies with `sudo apt install python3-spidev gpiod python3-libgpiod`; `python3-libgpiod` is optional when `gpioset` from `gpiod` is available. The `ext-board-codec` overlay shares pins with I2S and SPI functions, so avoid conflicting overlay combinations unless the user has confirmed the mux.

## Output style

For scripts, include:
- filename
- code block
- usage examples
- expected output or behavior
- short safety note if the script writes hardware state

Keep outputs minimal and practical.

## Bundled references

Consult `references/vim-5-minimal-hardware.md` for exact command patterns and helper examples.
