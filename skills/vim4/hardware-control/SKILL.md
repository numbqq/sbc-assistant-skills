---
name: khadas-vim4-hardware-control
description: minimal hardware control helper for Khadas VIM4 running Ubuntu 24.04. use when asked to generate, review, or debug Python or Bash scripts for LED, ADC, GPIO, PWM, I2C, SPI, OLED, UART, or fan control on VIM4. assumes fan control uses /usr/local/bin/fan.sh, LED control uses /sys/class/leds/pwmled, ADC uses /sys/bus/iio/devices/iio:device0/in_voltage*_raw, GPIO and PWM use wiringpi tools, I2C uses Linux /dev/i2c-* with Python ioctl helpers after checking the matching /dev/i2c-* node exists, SPI0 uses /dev/spidev1.0 after enabling the spi0 overlay, and UART_E uses /dev/ttyS4 after enabling the uart_e overlay.
---

# VIM4 Hardware Control

## Scope

Use this skill to help generate and troubleshoot minimal hardware-control scripts for Khadas VIM4 on Ubuntu 24.04.

Supported only:
- LED via `/sys/class/leds/pwmled`
- FAN via `/usr/local/bin/fan.sh`
- ADC via IIO sysfs raw nodes under `/sys/bus/iio/devices/iio:device0`
- GPIO via wiringpi
- PWM via wiringpi
- I2C via Linux `/dev/i2c-*` and Python `I2C_SLAVE` ioctl
- SPI0 via Linux `/dev/spidev1.0` and Python `SPI_IOC_MESSAGE` ioctl
- OLED over I2C via the bundled SSD1306 helper
- UART_E via Linux `/dev/ttyS4` and Python `termios`

For VIM4 40-pin I2C, SPI, or UART, check whether the matching device node exists. Do not treat overlay file contents as runtime status because `fdt_overlays` changes require reboot to take effect.

## Default assumptions

- Target board: Khadas VIM4 SBC
- OS: Ubuntu 24.04
- Script languages: Python or Bash
- `wiringpi` is installed and available for GPIO/PWM on the target system
- ADC header inputs are read-only raw IIO values with a 0 to 1.8V input range: PIN10 is ADC_CH6 at `/sys/bus/iio/devices/iio:device0/in_voltage6_raw`; PIN12 is ADC_CH3 at `/sys/bus/iio/devices/iio:device0/in_voltage3_raw`
- I2C access uses `/dev/i2c-<bus>` after the matching bus is exposed by the system
- 40-pin header PIN22/PIN23 are I2C5 when `i2cm_f` has been enabled and the system has rebooted
- 40-pin header PIN25/PIN26 are I2C0 when `i2cm_a` has been enabled and the system has rebooted
- 40-pin header PIN25/PIN26/PIN36/PIN37 are SPI0 when `spi0` has been enabled and the system has rebooted
- 40-pin header PIN15/PIN16 are UART_E when `uart_e` has been enabled and the system has rebooted
- I2C5, I2C0, SPI0, and UART_E header pins behave as normal GPIO by default until their overlay is enabled and active
- SPI0 shares PIN25/PIN26 with I2C0; do not enable or use both functions on those pins at the same time
- Fan is controlled by MCU through `/usr/local/bin/fan.sh`
- LED sysfs node is `/sys/class/leds/pwmled`

## Safety rules

Before generating commands that write hardware state:
1. Prefer discovery/read-only checks first.
2. Avoid hardcoding unknown pin numbers unless the user provided them.
3. Remind the user that GPIO/PWM pin numbering must match wiringpi numbering on the target board.
4. Use `sudo` only when needed for sysfs writes, wiringpi access, or `/dev/i2c-*` permissions.
5. For fan control, use `/usr/local/bin/fan.sh`; do not invent MCU register writes.
6. For ADC, read only the matching `in_voltage*_raw` file; do not treat ADC pins as digital GPIO outputs.
7. For I2C on bus 5 or bus 0, check `/dev/i2c-5` or `/dev/i2c-0` before I2C reads/writes.
8. For I2C writes, confirm the bus and address with read-only discovery first when possible.
9. For SPI0, check `/dev/spidev1.0` before SPI transfers.
10. For SPI writes/transfers, confirm SPI mode, speed, bits per word, chip-select wiring, and voltage level first when possible.
11. For UART_E, check `/dev/ttyS4` before serial reads/writes.
12. Remind users to cross-connect UART TX/RX, share GND, and use 3.3V TTL levels rather than RS-232 voltage levels.

## Workflow

1. Identify the requested hardware block: LED, FAN, ADC, GPIO, PWM, I2C, SPI, or UART.
2. Generate the smallest working Bash or Python script.
3. Include a read/check command when possible.
4. Include short usage examples.
5. Avoid Device Tree, kernel overlay, or driver rebuild steps except a short VIM4 40-pin I2C/SPI/UART note when the matching device node is missing.

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

## ADC through Linux IIO sysfs

Use raw IIO files:

```bash
/sys/bus/iio/devices/iio:device0/in_voltage6_raw
/sys/bus/iio/devices/iio:device0/in_voltage3_raw
```

40-pin header ADC mapping:
- PIN10 is ADC_CH6 at `/sys/bus/iio/devices/iio:device0/in_voltage6_raw`
- PIN12 is ADC_CH3 at `/sys/bus/iio/devices/iio:device0/in_voltage3_raw`
- ADC input voltage range is 0 to 1.8V

Useful checks:

```bash
scripts/vim4_hw_minimal.sh adc status
scripts/vim4_hw_minimal.sh adc read 6
scripts/vim4_hw_minimal.sh adc read 3
cat /sys/bus/iio/devices/iio:device0/in_voltage6_raw
cat /sys/bus/iio/devices/iio:device0/in_voltage3_raw
```

ADC raw values are board/driver raw readings. Do not convert raw values to voltage unless the raw resolution or IIO scale is known for the target image.

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
scripts/vim4_hw_minimal.sh gpio map
gpio mode <pin> out
gpio write <pin> 1
gpio write <pin> 0
gpio mode <pin> in
gpio read <pin>
```

Use `<pin>` as wiringpi pin number unless the user states another numbering scheme.

For the default VIM4 40-pin header state reported by `gpio readall`:
- Default digital GPIO inputs: physical PIN13/wPi1/GPIO420, PIN15/wPi2/GPIO491, PIN16/wPi3/GPIO490, PIN22/wPi6/GPIO501, PIN23/wPi7/GPIO502, PIN25/wPi8/GPIO466, PIN26/wPi9/GPIO467, PIN29/wPi10/GPIO447, PIN30/wPi11/GPIO446, PIN31/wPi12/GPIO449, PIN32/wPi13/GPIO448, PIN33/wPi14/GPIO450, PIN35/wPi15/GPIO492, PIN36/wPi16/GPIO464, and PIN37/wPi17/GPIO465.
- Alternate-function pins by default: physical PIN18/wPi4/GPIO413/PIN.D1, PIN19/wPi5/GPIO414/PIN.D2, and PIN39/wPi18/GPIO417/PIN.D5. Do not use them as generic GPIO examples unless intentionally switching their mode.
- Analog entries physical PIN10/wPi19/ADC_CH6 and PIN12/wPi20/ADC_CH3 do not show Linux GPIO numbers in the default table; treat them as ADC channels, not digital GPIO write targets.
- Non-GPIO header pins include 5V, 3V3, GND, VDD1V8, VCCMCU, HUB_D4N/HUB_D4P, MCUBOOT0, MCUSWDIO, and PWR_EN1.
- 40-pin I2C/SPI-capable pins are GPIO by default: PIN22/PIN23 are PIN.Y17/PIN.Y18 with pull-up/high defaults and become I2C5 only after `i2cm_f` is active; PIN25/PIN26 are PIN.T20/PIN.T21 with pull-down defaults and become I2C0 only after `i2cm_a` is active; PIN25/PIN26/PIN36/PIN37 become SPI0 only after `spi0` is active. SPI0 and I2C0 share PIN25/PIN26, so use only one of those functions at a time.
- 40-pin UART-capable pins are GPIO by default: PIN15/PIN16 are PIN.Y7/PIN.Y6 and become UART_E RX/TX only after `uart_e` is active.

## PWM through wiringpi

Use wiringpi PWM only when the selected pin supports PWM. Use conservative examples:

```bash
gpio mode <pin> pwm
gpio pwm <pin> <value>
```

If range/clock settings are needed, expose them as parameters and warn that valid values depend on wiringpi support for the selected pin.

## I2C through Linux i2c-dev

For I2C tasks, do not use wiringpi. Use Linux `/dev/i2c-*` device nodes and Python helpers based on `fcntl.ioctl(fd, I2C_SLAVE, addr)`.

For 40-pin header I2C:
- PIN22/PIN23 are I2C5 and require `fdt_overlays=i2cm_f`
- PIN25/PIN26 are I2C0 and require `fdt_overlays=i2cm_a`
- The overlay config file is `/boot/dtb/amlogic/kvim4.dtb.overlay.env`
- `fdt_overlays` changes require reboot, so runtime readiness is determined by `/dev/i2c-5` or `/dev/i2c-0`
- If the node is missing, explain that I2C is not active on that header bus; the pins remain normal GPIO until the overlay is enabled and the system reboots

Useful checks:

```bash
scripts/vim4_hw_minimal.sh i2c status 5
scripts/vim4_hw_minimal.sh i2c status 0
i2cdetect -l
ls -l /dev/i2c-<bus>
i2cdetect -y <bus>
```

Bundled helpers:

```bash
scripts/i2c_read_write.py read --bus 5 --addr 0x40 --reg 0x00
scripts/i2c_read_write.py write --bus 5 --addr 0x40 --reg 0x01 --value 0xff
scripts/i2c_read_write.py write-bytes --bus 5 --addr 0x3c --data 0x00 0xae
scripts/oled_ssd1306_demo.py --bus 5 --addr 0x3c
```

Keep bus number, device address, register, and raw bytes configurable. Prefer no external Python dependency for I2C; use `smbus2` only if the user explicitly requests SMBus APIs.

## SPI through Linux spidev

For VIM4 40-pin header SPI:
- PIN25/PIN26/PIN36/PIN37 are SPI0 and require `fdt_overlays=spi0`
- Device node is `/dev/spidev1.0`
- SPI0 shares PIN25/PIN26 with I2C0; do not use SPI0 and I2C0 on those pins at the same time
- The overlay config file is `/boot/dtb/amlogic/kvim4.dtb.overlay.env`
- `fdt_overlays` changes require reboot, so runtime readiness is determined by `/dev/spidev1.0`
- If the node is missing, explain that SPI0 is not active on PIN25/PIN26/PIN36/PIN37; enable `spi0` and reboot

Useful checks:

```bash
scripts/vim4_hw_minimal.sh spi status
ls -l /dev/spidev1.0
```

Enable note:

```bash
# Edit /boot/dtb/amlogic/kvim4.dtb.overlay.env so fdt_overlays includes spi0, then reboot.
fdt_overlays=spi0
```

Bundled helper:

```bash
scripts/spi_transfer.py transfer --device /dev/spidev1.0 --mode 0 --speed 500000 --data 0x9f 0x00 0x00 0x00
scripts/vim4_hw_minimal.sh spi transfer 0x9f 0x00 0x00 0x00
```

Keep device path, mode, speed, bits per word, and byte payload configurable. Prefer the bundled stdlib ioctl helper; use `spidev` Python packages only if the user explicitly requests them.

## UART through Linux tty

For VIM4 40-pin header UART:
- PIN15 is UART_E RX
- PIN16 is UART_E TX
- Device node is `/dev/ttyS4`
- Required overlay is `uart_e`
- The overlay config file is `/boot/dtb/amlogic/kvim4.dtb.overlay.env`
- `fdt_overlays` changes require reboot, so runtime readiness is determined by `/dev/ttyS4`
- If the node is missing, explain that UART_E is not active on PIN15/PIN16; enable `uart_e` and reboot

Useful checks:

```bash
scripts/vim4_hw_minimal.sh uart status
ls -l /dev/ttyS4
```

Enable note:

```bash
# Edit /boot/dtb/amlogic/kvim4.dtb.overlay.env so fdt_overlays includes uart_e, then reboot.
fdt_overlays=uart_e
```

Bundled helper:

```bash
scripts/uart_read_write.py send --device /dev/ttyS4 --baud 115200 --text "hello"
scripts/uart_read_write.py receive --device /dev/ttyS4 --baud 115200 --timeout 5
scripts/uart_read_write.py loopback --device /dev/ttyS4 --baud 115200 --text "hello"
```

Keep device path, baud rate, timeout, and payload configurable. Prefer the bundled stdlib `termios` helper; use `pyserial` only if the user explicitly requests it.

## Output style

For scripts, include:
- filename
- code block
- usage examples
- expected output or behavior
- short safety note if the script writes hardware state

Keep outputs minimal and practical.

## Bundled references

Consult `references/vim4-minimal-hardware.md` for exact command patterns and helper examples.
