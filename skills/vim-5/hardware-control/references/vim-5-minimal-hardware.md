# VIM 5 Minimal Hardware Reference

## Target

- Board: Khadas VIM 5
- OS: Ubuntu 24.04
- ADC: Linux IIO sysfs input nodes or wiringpi `gpio aread`, 0 to 1.8V input range
- GPIO/PWM: wiringpi
- I2C: Linux `/dev/i2c-*` plus Python `I2C_SLAVE` ioctl helpers
- SPI: Linux `/dev/spidev1.0` plus Python `SPI_IOC_MESSAGE` ioctl helper
- UART: Linux `/dev/ttyS4` plus Python `termios` helper
- Func key: Linux input `/dev/input/event3` with device name `adc_keypad`
- LED: `/sys/class/leds/pwmled`
- FAN: `/usr/local/bin/fan.sh`
- Expansion-board green LED: `/sys/class/leds/green_led`
- Expansion-board analog MIC: `ext-board-codec` overlay, ALSA route setup, capture device `hw:0,1`
- Mic Array: ALSA capture device `hw:0,3`
- Expansion-board three-wire SPI OLED/LCD: `spi1-lcd` overlay, `/dev/spidev1.0`, bundled ST7735 helper `scripts/spi_lcd_st7735.py`

## Runtime dependency preflight

Check dependencies before running hardware operations. If a command or Python module is missing, install the package first, rerun the check, then run the program.

Common checks:

```bash
command -v python3
command -v gpio        # wiringpi GPIO/PWM/ADC command
command -v i2cdetect   # package: i2c-tools
command -v amixer      # package: alsa-utils
command -v arecord     # package: alsa-utils
python3 -c 'import sys; print(sys.executable)'
python3 -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("spidev") else 1)'
dpkg-query -W -f='${Status}\n' python3-spidev
command -v gpioset || python3 -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("gpiod") else 1)'
```

Known apt packages:

```bash
sudo apt update
sudo apt install i2c-tools
sudo apt install alsa-utils
sudo apt install python3-spidev gpiod python3-libgpiod
```

For GPIO/PWM and wiringpi ADC reads, install the VIM 5 image's Khadas/wiringpi package when `gpio` is missing. On images that provide an apt package, try:

```bash
sudo apt install wiringpi
```

Bundled I2C, SSD1306 OLED, SPI transfer, UART, and Func key Python helpers use the Python standard library by default. Do not install `smbus2`, external `spidev`, or `pyserial` for those helpers unless the task explicitly requests those APIs. The expansion-board ST7735 SPI LCD helper is the exception: it requires `python3-spidev` and needs either `gpioset` from `gpiod` or the Python `gpiod` module.

If `python3-spidev` is installed but the script still reports `missing python spidev module`, check the active interpreter:

```bash
python3 -c 'import sys; print(sys.executable); import spidev; print(spidev.__file__)'
/usr/bin/python3 -c 'import sys; print(sys.executable); import spidev; print(spidev.__file__)'
```

When `/usr/bin/python3` can import `spidev` but `python3` cannot, the active shell is using a Conda/base or virtualenv Python that cannot see apt packages under `/usr/lib/python3/dist-packages`. Use one of:

```bash
conda deactivate
/usr/bin/python3 scripts/spi_lcd_sys_monitor.py --interval 1
```

Alternatively, install a compatible `spidev` module into the active Python environment. Prefer `/usr/bin/python3` for VIM 5 hardware scripts that rely on Ubuntu apt packages.

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

Expansion-board green LED:

```bash
GREEN_LED=/sys/class/leds/green_led
cat $GREEN_LED/max_brightness
cat $GREEN_LED/brightness
echo 1 | sudo tee $GREEN_LED/brightness
scripts/vim-5_hw_minimal.sh ext-board green-led status
scripts/vim-5_hw_minimal.sh ext-board green-led brightness 1
python3 scripts/led_blink.py --led-path /sys/class/leds/green_led --delay 0.1
```

Use `/sys/class/leds/pwmled` for the VIM 5 board LED and `/sys/class/leds/green_led` for the expansion-board green LED.

## GPIO wiringpi commands

```bash
gpio readall
scripts/vim-5_hw_minimal.sh gpio map
gpio mode <pin> out
gpio write <pin> 1
gpio write <pin> 0
gpio mode <pin> in
gpio read <pin>
```

Use wiringpi pin numbering by default. In `gpio readall`, the `wPi` column is the pin number used by `gpio mode`, `gpio read`, `gpio write`, and `gpio pwm`. The `GPIO` column is the Linux/global GPIO number reported by wiringpi; do not pass it to wiringpi commands unless the command explicitly asks for a Linux GPIO number.

### Default 40-pin GPIO state

This is the default 40-pin header state from `gpio readall` on Khadas VIM 5. Confirm the live board with `gpio readall` because `gpio mode`, active overlays, and attached hardware can change mode, value, and pull state.

| Physical | wPi | GPIO | Name | Default mode | V | Pull | Notes |
| --- | ---: | ---: | --- | --- | ---: | --- | --- |
| 13 | 1 | 641 | PIN.D13 | IN | 0 | P/D | GPIO by default; becomes SPDIF when `spdifout` is active. |
| 15 | 2 | 637 | PIN.D9 | IN | 0 | P/U | GPIO by default; becomes UART RX when `uart_ao_e` is active. |
| 16 | 3 | 636 | PIN.D8 | IN | 0 | P/D | GPIO by default; becomes UART TX when `uart_ao_e` is active. |
| 18 | 4 | 629 | PIN.D1 | ALT0 | 1 | P/U | Alternate function by default; avoid unless intentionally remuxing. |
| 19 | 5 | 628 | PIN.D0 | ALT0 | 1 | P/U | Alternate function by default; avoid unless intentionally remuxing. |
| 22 | 6 | 591 | PIN.A15 | IN | 1 | P/D | GPIO by default; becomes I2C3 when `i2c_d` is active. |
| 23 | 7 | 590 | PIN.A14 | IN | 1 | P/D | GPIO by default; becomes I2C3 when `i2c_d` is active. |
| 25 | 8 | 555 | PIN.M1 | IN | 1 | P/D | GPIO by default; becomes I2C6 when `i2c_g` is active; also shared with SPI1 when `spi1` is active. |
| 26 | 9 | 554 | PIN.M0 | IN | 1 | P/D | GPIO by default; becomes I2C6 when `i2c_g` is active; also shared with SPI1 when `spi1` is active. |
| 29 | 10 | 577 | PIN.A1 | IN | 0 | P/D | GPIO input by default. |
| 30 | 11 | 576 | PIN.A0 | IN | 0 | P/D | GPIO input by default. |
| 31 | 12 | 579 | PIN.A3 | IN | 0 | P/D | GPIO input by default. |
| 32 | 13 | 578 | PIN.A2 | IN | 0 | P/D | GPIO input by default. |
| 33 | 14 | 580 | PIN.A4 | IN | 0 | P/D | GPIO input by default. |
| 35 | 15 | 601 | PIN.Y5 | IN | 1 | P/U | GPIO by default; becomes PWM when `pwm_j` is active. |
| 36 | 16 | 556 | PIN.M2 | IN | 1 | P/D | GPIO by default; becomes SPI1 when `spi1` is active. |
| 37 | 17 | 557 | PIN.M3 | IN | 1 | P/D | GPIO by default; becomes SPI1 when `spi1` is active. |
| 39 | 18 | 633 | PIN.D5 | IN | 1 | P/U | GPIO by default; becomes IR when `ir` is active. |

ADC entries in the default table:

| Physical | wPi | Name | Notes |
| --- | ---: | --- | --- |
| 10 | 19 | ADC0 | Analog channel at `/sys/bus/iio/devices/iio:device0/in_voltage0_input`; wiringpi command is `gpio aread 19`; 0 to 1.8V input range; no Linux GPIO number is reported in the default table. |
| 12 | 20 | ADC1 | Analog channel at `/sys/bus/iio/devices/iio:device0/in_voltage3_input`; wiringpi command is `gpio aread 20`; 0 to 1.8V input range; no Linux GPIO number is reported in the default table. |

Non-GPIO or reserved/power pins in the default table:

| Physical pins | Name |
| --- | --- |
| 1, 2 | 5V |
| 20, 27 | 3V3 |
| 5, 9, 14, 17, 21, 24, 28, 34, 40 | GND |
| 11 | 1.8V |
| 6 | MCU3.3 |
| 3, 4 | USB_DM/USB_DP |
| 7 | MCUNRST |
| 8 | MCUSWIM |
| 38 | PWR_HOLD |

Practical GPIO selection rules:

- For simple digital examples, prefer pins that are already `IN` by default and have both `wPi` and `GPIO` numbers.
- Use `gpio mode <wPi> out` before `gpio write <wPi> <0|1>`.
- Avoid default `ALT0` pins unless the task explicitly asks to repurpose that signal.
- Do not use ADC-only `wPi` entries as digital GPIO outputs.

## PWM wiringpi commands

PIN35/wPi15/GPIO601 is GPIO by default and becomes PWM only after the `pwm_j` overlay is enabled and the system has rebooted.

```bash
scripts/vim-5_hw_minimal.sh pwm status
gpio mode <pin> pwm
gpio pwm <pin> <value>
```

Only use pins that support PWM.

## ADC commands

PIN10 and PIN12 are ADC inputs, not digital GPIO outputs. The ADC input voltage range is 0 to 1.8V. Read values through Linux IIO sysfs or wiringpi ADC reads:

| Header pin | Header ADC | IIO input node | Wiringpi command |
| --- | --- | --- | --- |
| PIN10 | ADC0 | `/sys/bus/iio/devices/iio:device0/in_voltage0_input` | `gpio aread 19` |
| PIN12 | ADC1 | `/sys/bus/iio/devices/iio:device0/in_voltage3_input` | `gpio aread 20` |

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

Keep ADC examples read-only. IIO input values are driver readings; only convert them again when the target system's units or IIO scale are known.

## I2C commands

### 40-pin header I2C readiness

On VIM 5, the 40-pin header I2C pins are GPIO by default until the matching Device Tree overlay is enabled and the system has rebooted:

| Header pins | I2C bus | Required overlay |
| --- | --- | --- |
| PIN22/PIN23 | I2C3 | `i2c_d` |
| PIN25/PIN26 | I2C6 | `i2c_g` |

Overlay config file:

```bash
/boot/dtb/amlogic/kvim-5.dtb.overlay.env
```

Overlay files directory:

```bash
/boot/dtb/amlogic/kvim-5.dtb.overlays
```

Because `fdt_overlays` changes require reboot, runtime readiness is determined by the device node. Check the node before I2C access:

```bash
scripts/vim-5_hw_minimal.sh i2c status 3
scripts/vim-5_hw_minimal.sh i2c status 6
i2cdetect -l
ls -l /dev/i2c-3 /dev/i2c-6
```

If `/dev/i2c-3` is missing, explain that PIN22/PIN23 are not active as I2C3; enable `i2c_d` and reboot. If `/dev/i2c-6` is missing, explain that PIN25/PIN26 are not active as I2C6; enable `i2c_g` and reboot.

```bash
i2cdetect -l
ls -l /dev/i2c-<bus>
i2cdetect -y <bus>
```

For Python I2C access, use the bundled helper. It does not require `smbus2`:

```bash
sudo python3 scripts/i2c_read_write.py read --bus 3 --addr 0x40 --reg 0x00
sudo python3 scripts/i2c_read_write.py read --bus 3 --addr 0x40 --reg 0x00 --length 4
sudo python3 scripts/i2c_read_write.py write --bus 3 --addr 0x40 --reg 0x01 --value 0xff
sudo python3 scripts/i2c_read_write.py write-bytes --bus 3 --addr 0x3c --data 0x00 0xae
sudo python3 scripts/i2c_read_write.py read-raw --bus 3 --addr 0x40 --length 4
```

For SSD1306-compatible OLED displays:

```bash
sudo python3 scripts/oled_ssd1306_demo.py --bus 3 --addr 0x3c
sudo python3 scripts/oled_ssd1306_demo.py --bus 3 --addr 0x3c --fill
```

Keep bus, address, register, and byte payload configurable in generated examples.

## SPI commands

### 40-pin header SPI readiness

On VIM 5, the 40-pin header SPI pins are GPIO by default until the SPI1 Device Tree overlay is enabled and the system has rebooted. SPI1 shares PIN25/PIN26 with I2C6, so do not use SPI1 and I2C6 on those pins at the same time.

| Header pins | SPI bus | Required overlay | Device node |
| --- | --- | --- | --- |
| PIN25/PIN26/PIN36/PIN37 | SPI1 | `spi1` | `/dev/spidev1.0` |

Overlay config file:

```bash
/boot/dtb/amlogic/kvim-5.dtb.overlay.env
```

Overlay files directory:

```bash
/boot/dtb/amlogic/kvim-5.dtb.overlays
```

Because `fdt_overlays` changes require reboot, runtime readiness is determined by the device node. Check the node before SPI access:

```bash
scripts/vim-5_hw_minimal.sh spi status
ls -l /dev/spidev1.0
```

If `/dev/spidev1.0` is missing, explain that PIN25/PIN26/PIN36/PIN37 are not active as SPI1; enable `spi1` and reboot.

To enable SPI1, edit `/boot/dtb/amlogic/kvim-5.dtb.overlay.env` so `fdt_overlays` includes `spi1`, then reboot:

```bash
fdt_overlays=spi1
```

For Python SPI access, use the bundled helper. It does not require the external `spidev` Python package:

```bash
sudo python3 scripts/spi_transfer.py status --device /dev/spidev1.0
sudo python3 scripts/spi_transfer.py transfer --device /dev/spidev1.0 --mode 0 --speed 500000 --data 0x9f 0x00 0x00 0x00
scripts/vim-5_hw_minimal.sh spi transfer 0x9f 0x00 0x00 0x00
```

Keep device path, SPI mode, speed, bits per word, and byte payload configurable in generated examples.

## UART commands

### 40-pin header UART readiness

On VIM 5, PIN15/PIN16 are GPIO by default until the UART Device Tree overlay is enabled and the system has rebooted:

| Header pins | UART | Direction | Required overlay | Device node |
| --- | --- | --- | --- | --- |
| PIN15 | UART | RX | `uart_ao_e` | `/dev/ttyS4` |
| PIN16 | UART | TX | `uart_ao_e` | `/dev/ttyS4` |

Overlay config file:

```bash
/boot/dtb/amlogic/kvim-5.dtb.overlay.env
```

Overlay files directory:

```bash
/boot/dtb/amlogic/kvim-5.dtb.overlays
```

Because `fdt_overlays` changes require reboot, runtime readiness is determined by the device node. Check the node before UART access:

```bash
scripts/vim-5_hw_minimal.sh uart status
ls -l /dev/ttyS4
```

If `/dev/ttyS4` is missing, explain that PIN15/PIN16 are not active as UART; enable `uart_ao_e` and reboot.

To enable UART, edit `/boot/dtb/amlogic/kvim-5.dtb.overlay.env` so `fdt_overlays` includes `uart_ao_e`, then reboot:

```bash
fdt_overlays=uart_ao_e
```

For Python UART access, use the bundled helper. It does not require `pyserial`:

```bash
sudo python3 scripts/uart_read_write.py send --device /dev/ttyS4 --baud 115200 --text "hello"
sudo python3 scripts/uart_read_write.py receive --device /dev/ttyS4 --baud 115200 --timeout 5
sudo python3 scripts/uart_read_write.py loopback --device /dev/ttyS4 --baud 115200 --text "hello"
```

Use 3.3V TTL UART wiring. Cross-connect TX/RX between devices and connect GND.

## Func key commands

The board Func key is exposed as a Linux input event device:

```bash
/dev/input/event3
```

The expected device name is `adc_keypad`. Treat this as read-only input, not as GPIO, PWM, or a raw ADC channel.

Useful checks:

```bash
scripts/vim-5_hw_minimal.sh key status
scripts/vim-5_hw_minimal.sh key wait 10
scripts/vim-5_hw_minimal.sh key listen
```

For direct Python access, use the bundled helper. It uses only the Python standard library:

```bash
python3 scripts/key_input.py status
python3 scripts/key_input.py wait --timeout 10
python3 scripts/key_input.py listen
```

If reading `/dev/input/event3` fails with permission denied, run with `sudo` or add the user to the Linux `input` group.

## Expansion-board commands

The VIM 5 expansion board provides a green LED, analog MIC, Mic Array, and a three-wire SPI OLED/LCD. The overlay config file is:

```bash
/boot/dtb/amlogic/kvim-5.dtb.overlay.env
```

Overlay files live under:

```bash
/boot/dtb/amlogic/kvim-5.dtb.overlays
```

### Expansion-board status

```bash
scripts/vim-5_hw_minimal.sh ext-board status
scripts/vim-5_hw_minimal.sh ext-board analog-mic status
scripts/vim-5_hw_minimal.sh ext-board mic-array status
scripts/vim-5_hw_minimal.sh ext-board spi-lcd status
```

### Analog MIC

Requirements:

- Expansion board connected
- `fdt_overlays=ext-board-codec`
- Reboot after changing `fdt_overlays`

The analog MIC overlay shares pins with I2S and SPI functions. Do not enable or use conflicting overlays at the same time unless the mux configuration has been confirmed.

Configure the route:

```bash
amixer -c 0 cset name='TDMIN_B source select' 'tdmin_b'
scripts/vim-5_hw_minimal.sh ext-board analog-mic configure
```

Record 10 seconds:

```bash
arecord -D hw:0,1 -f cd -c 2 -d 10 test.wav
scripts/vim-5_hw_minimal.sh ext-board analog-mic record 10 test.wav
```

### Mic Array

Record 10 seconds from the 6-channel PDM Mic Array:

```bash
arecord -Dhw:0,3 -r 48000 -f S16_LE -c 6 -d 10 pdm_6ch.wav
scripts/vim-5_hw_minimal.sh ext-board mic-array record 10 pdm_6ch.wav
```

### Three-wire SPI OLED/LCD

Requirements:

- Expansion board connected
- `fdt_overlays=spi1-lcd`
- Reboot after changing `fdt_overlays`
- Runtime node `/dev/spidev1.0`
- Dependencies: `python3-spidev`, `gpiod`, and optionally `python3-libgpiod`

Install dependencies:

```bash
sudo apt update
sudo apt install python3-spidev gpiod python3-libgpiod
```

`python3-libgpiod` is optional when `gpioset` from package `gpiod` is available. The helper accepts either named lines or explicit chip/line values:

```bash
--reset-line GPIOD_5 --dc-line GPIOM_1
--reset-line gpiochip10:5 --dc-line gpiochip3:1
```

Check readiness:

```bash
scripts/vim-5_hw_minimal.sh ext-board spi-lcd status
ls -l /dev/spidev1.0
```

Draw the default VIM 5 test frame:

```bash
scripts/vim-5_hw_minimal.sh ext-board spi-lcd test
python3 scripts/spi_lcd_st7735.py test
```

Clear the panel:

```bash
scripts/vim-5_hw_minimal.sh ext-board spi-lcd clear black
python3 scripts/spi_lcd_st7735.py clear --color black
```

Draw text:

```bash
scripts/vim-5_hw_minimal.sh ext-board spi-lcd text "Khadas" "VIM 5"
python3 scripts/spi_lcd_st7735.py text --line "Khadas" --line "VIM 5"
```

If GPIO name resolution does not work, pass explicit lines directly to the Python helper:

```bash
python3 scripts/spi_lcd_st7735.py test \
  --spi /dev/spidev1.0 \
  --reset-line gpiochip10:5 \
  --dc-line gpiochip3:1
```
