# VIM4 Minimal Hardware Reference

## Target

- Board: Khadas VIM4
- OS: Ubuntu 24.04
- GPIO/PWM: wiringpi
- I2C: Linux `/dev/i2c-*` plus Python `I2C_SLAVE` ioctl helpers
- SPI: Linux `/dev/spidev1.0` plus Python `SPI_IOC_MESSAGE` ioctl helper
- UART: Linux `/dev/ttyS4` plus Python `termios` helper
- LED: `/sys/class/leds/pwmled`
- FAN: `/usr/local/bin/fan.sh`

## Fan commands

The fan is controlled by MCU. Use only the official helper script:

```bash
/usr/local/bin/fan.sh on      # set fan mode on
/usr/local/bin/fan.sh auto    # set fan mode auto
/usr/local/bin/fan.sh off     # set fan mode off
/usr/local/bin/fan.sh low     # set fan level low
/usr/local/bin/fan.sh mid     # set fan level mid
/usr/local/bin/fan.sh high    # set fan level high
/usr/local/bin/fan.sh temp    # query cpu temperature
/usr/local/bin/fan.sh trig    # query fan trigger temperature
/usr/local/bin/fan.sh mode    # query fan mode/level
/usr/local/bin/fan.sh -h      # help
```

## LED commands

```bash
LED=/sys/class/leds/pwmled
cat $LED/max_brightness
cat $LED/brightness
echo 1 | sudo tee $LED/brightness
```

For unknown brightness range, read `max_brightness` first.

## GPIO wiringpi commands

```bash
gpio readall
scripts/vim4_hw_minimal.sh gpio map
gpio mode <pin> out
gpio write <pin> 1
gpio write <pin> 0
gpio mode <pin> in
gpio read <pin>
```

Use wiringpi pin numbering by default. In `gpio readall`, the `wPi` column is the pin number used by `gpio mode`, `gpio read`, `gpio write`, and `gpio pwm`. The `GPIO` column is the Linux/global GPIO number reported by wiringpi; do not pass it to wiringpi commands unless the command explicitly asks for a Linux GPIO number.

### Default 40-pin GPIO state

This is the default 40-pin header state from `gpio readall` on Khadas VIM4. Confirm the live board with `gpio readall` because `gpio mode`, active overlays, and attached hardware can change mode, value, and pull state.

| Physical | wPi | GPIO | Name | Default mode | V | Pull | Notes |
| --- | ---: | ---: | --- | --- | ---: | --- | --- |
| 13 | 1 | 420 | SPDIFOUT | IN | 0 | P/D | GPIO-capable; name indicates an alternate SPDIF signal. |
| 15 | 2 | 491 | PIN.Y7 | IN | 0 | P/D | GPIO by default; becomes UART_E RX when `uart_e` is active. |
| 16 | 3 | 490 | PIN.Y6 | IN | 1 | P/U | GPIO by default; becomes UART_E TX when `uart_e` is active. |
| 18 | 4 | 413 | PIN.D1 | ALT0 | 1 | P/U | Alternate function by default; avoid unless intentionally remuxing. |
| 19 | 5 | 414 | PIN.D2 | ALT0 | 1 | DSBLD | Alternate function by default; avoid unless intentionally remuxing. |
| 22 | 6 | 501 | PIN.Y17 | IN | 1 | P/U | GPIO by default; becomes I2C5 when `i2cm_f` is active. |
| 23 | 7 | 502 | PIN.Y18 | IN | 1 | P/U | GPIO by default; becomes I2C5 when `i2cm_f` is active. |
| 25 | 8 | 466 | PIN.T20 | IN | 1 | P/D | GPIO by default; becomes I2C0 when `i2cm_a` is active; also shared with SPI0 when `spi0` is active. |
| 26 | 9 | 467 | PIN.T21 | IN | 1 | P/D | GPIO by default; becomes I2C0 when `i2cm_a` is active; also shared with SPI0 when `spi0` is active. |
| 29 | 10 | 447 | PIN.T1 | IN | 0 | P/D | GPIO input by default. |
| 30 | 11 | 446 | PIN.T0 | IN | 0 | P/D | GPIO input by default. |
| 31 | 12 | 449 | PIN.T3 | IN | 0 | P/D | GPIO input by default. |
| 32 | 13 | 448 | PIN.T2 | IN | 0 | P/D | GPIO input by default. |
| 33 | 14 | 450 | PIN.T4 | IN | 0 | P/D | GPIO input by default. |
| 35 | 15 | 492 | PIN.Y8 | IN | 0 | P/D | GPIO input by default. |
| 36 | 16 | 464 | PIN.T18 | IN | 0 | P/D | GPIO by default; becomes SPI0 when `spi0` is active. |
| 37 | 17 | 465 | PIN.T19 | IN | 0 | P/D | GPIO by default; becomes SPI0 when `spi0` is active. |
| 39 | 18 | 417 | PIN.D5 | ALT0 | 0 | DSBLD | Alternate function by default; avoid unless intentionally remuxing. |

ADC entries in the default table:

| Physical | wPi | Name | Notes |
| --- | ---: | --- | --- |
| 10 | 19 | ADC_CH6 | Analog channel; no Linux GPIO number is reported in the default table. |
| 12 | 20 | ADC_CH3 | Analog channel; no Linux GPIO number is reported in the default table. |

Non-GPIO or reserved/power pins in the default table:

| Physical pins | Name |
| --- | --- |
| 1, 2 | 5V |
| 20, 27 | 3V3 |
| 5, 9, 14, 21, 24, 28, 34, 40 | GND |
| 11 | VDD1V8 |
| 6 | VCCMCU |
| 3, 4 | HUB_D4N/HUB_D4P |
| 7, 8 | MCUBOOT0/MCUSWDIO |
| 38 | PWR_EN1 |

Practical GPIO selection rules:

- For simple digital examples, prefer pins that are already `IN` by default and have both `wPi` and `GPIO` numbers.
- Use `gpio mode <wPi> out` before `gpio write <wPi> <0|1>`.
- Avoid default `ALT0` pins unless the task explicitly asks to repurpose that signal.
- Do not use ADC-only `wPi` entries as digital GPIO outputs.

## PWM wiringpi commands

```bash
gpio mode <pin> pwm
gpio pwm <pin> <value>
```

Only use pins that support PWM.

## I2C commands

### 40-pin header I2C readiness

On VIM4, the 40-pin header I2C pins are GPIO by default until the matching Device Tree overlay is enabled and the system has rebooted:

| Header pins | I2C bus | Required overlay |
| --- | --- | --- |
| PIN22/PIN23 | I2C5 | `i2cm_f` |
| PIN25/PIN26 | I2C0 | `i2cm_a` |

Overlay config file:

```bash
/boot/dtb/amlogic/kvim4.dtb.overlay.env
```

Because `fdt_overlays` changes require reboot, runtime readiness is determined by the device node. Check the node before I2C access:

```bash
scripts/vim4_hw_minimal.sh i2c status 5
scripts/vim4_hw_minimal.sh i2c status 0
i2cdetect -l
ls -l /dev/i2c-5 /dev/i2c-0
```

If `/dev/i2c-5` is missing, explain that PIN22/PIN23 are not active as I2C5; enable `i2cm_f` and reboot. If `/dev/i2c-0` is missing, explain that PIN25/PIN26 are not active as I2C0; enable `i2cm_a` and reboot.

```bash
i2cdetect -l
ls -l /dev/i2c-<bus>
i2cdetect -y <bus>
```

For Python I2C access, use the bundled helper. It does not require `smbus2`:

```bash
sudo python3 scripts/i2c_read_write.py read --bus 5 --addr 0x40 --reg 0x00
sudo python3 scripts/i2c_read_write.py read --bus 5 --addr 0x40 --reg 0x00 --length 4
sudo python3 scripts/i2c_read_write.py write --bus 5 --addr 0x40 --reg 0x01 --value 0xff
sudo python3 scripts/i2c_read_write.py write-bytes --bus 5 --addr 0x3c --data 0x00 0xae
sudo python3 scripts/i2c_read_write.py read-raw --bus 5 --addr 0x40 --length 4
```

For SSD1306-compatible OLED displays:

```bash
sudo python3 scripts/oled_ssd1306_demo.py --bus 5 --addr 0x3c
sudo python3 scripts/oled_ssd1306_demo.py --bus 5 --addr 0x3c --fill
```

Keep bus, address, register, and byte payload configurable in generated examples.

## SPI commands

### 40-pin header SPI readiness

On VIM4, the 40-pin header SPI pins are GPIO by default until the SPI0 Device Tree overlay is enabled and the system has rebooted. SPI0 shares PIN25/PIN26 with I2C0, so do not use SPI0 and I2C0 on those pins at the same time.

| Header pins | SPI bus | Required overlay | Device node |
| --- | --- | --- | --- |
| PIN25/PIN26/PIN36/PIN37 | SPI0 | `spi0` | `/dev/spidev1.0` |

Overlay config file:

```bash
/boot/dtb/amlogic/kvim4.dtb.overlay.env
```

Because `fdt_overlays` changes require reboot, runtime readiness is determined by the device node. Check the node before SPI access:

```bash
scripts/vim4_hw_minimal.sh spi status
ls -l /dev/spidev1.0
```

If `/dev/spidev1.0` is missing, explain that PIN25/PIN26/PIN36/PIN37 are not active as SPI0; enable `spi0` and reboot.

To enable SPI0, edit `/boot/dtb/amlogic/kvim4.dtb.overlay.env` so `fdt_overlays` includes `spi0`, then reboot:

```bash
fdt_overlays=spi0
```

For Python SPI access, use the bundled helper. It does not require the external `spidev` Python package:

```bash
sudo python3 scripts/spi_transfer.py status --device /dev/spidev1.0
sudo python3 scripts/spi_transfer.py transfer --device /dev/spidev1.0 --mode 0 --speed 500000 --data 0x9f 0x00 0x00 0x00
scripts/vim4_hw_minimal.sh spi transfer 0x9f 0x00 0x00 0x00
```

Keep device path, SPI mode, speed, bits per word, and byte payload configurable in generated examples.

## UART commands

### 40-pin header UART readiness

On VIM4, PIN15/PIN16 are GPIO by default until the UART_E Device Tree overlay is enabled and the system has rebooted:

| Header pins | UART | Direction | Required overlay | Device node |
| --- | --- | --- | --- | --- |
| PIN15 | UART_E | RX | `uart_e` | `/dev/ttyS4` |
| PIN16 | UART_E | TX | `uart_e` | `/dev/ttyS4` |

Overlay config file:

```bash
/boot/dtb/amlogic/kvim4.dtb.overlay.env
```

Because `fdt_overlays` changes require reboot, runtime readiness is determined by the device node. Check the node before UART access:

```bash
scripts/vim4_hw_minimal.sh uart status
ls -l /dev/ttyS4
```

If `/dev/ttyS4` is missing, explain that PIN15/PIN16 are not active as UART_E; enable `uart_e` and reboot.

To enable UART_E, edit `/boot/dtb/amlogic/kvim4.dtb.overlay.env` so `fdt_overlays` includes `uart_e`, then reboot:

```bash
fdt_overlays=uart_e
```

For Python UART access, use the bundled helper. It does not require `pyserial`:

```bash
sudo python3 scripts/uart_read_write.py send --device /dev/ttyS4 --baud 115200 --text "hello"
sudo python3 scripts/uart_read_write.py receive --device /dev/ttyS4 --baud 115200 --timeout 5
sudo python3 scripts/uart_read_write.py loopback --device /dev/ttyS4 --baud 115200 --text "hello"
```

Use 3.3V TTL UART wiring. Cross-connect TX/RX between devices and connect GND.
