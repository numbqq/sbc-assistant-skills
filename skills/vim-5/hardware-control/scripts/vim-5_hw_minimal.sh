#!/usr/bin/env bash
set -euo pipefail

LED_PATH="/sys/class/leds/pwmled"
EXT_GREEN_LED_PATH="/sys/class/leds/green_led"
FAN_SCRIPT="/usr/local/bin/fan.sh"
IIO_DEVICE="/sys/bus/iio/devices/iio:device0"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
I2C_HELPER="$SCRIPT_DIR/i2c_read_write.py"
OLED_HELPER="$SCRIPT_DIR/oled_ssd1306_demo.py"
SPI_HELPER="$SCRIPT_DIR/spi_transfer.py"
SPI_LCD_HELPER="$SCRIPT_DIR/spi_lcd_st7735.py"
SPI_DEVICE="/dev/spidev1.0"
SPI_OVERLAY="spi1"
UART_HELPER="$SCRIPT_DIR/uart_read_write.py"
UART_DEVICE="/dev/ttyS4"
UART_OVERLAY="uart_ao_e"
KEY_HELPER="$SCRIPT_DIR/key_input.py"
KEY_DEVICE="/dev/input/event3"
KEY_NAME="adc_keypad"
GSENSOR_HELPER="$SCRIPT_DIR/gsensor_input.py"
GSENSOR_DEVICE="/dev/input/event0"
GSENSOR_NAME="kxtj3_accel"
OVERLAY_CONFIG="/boot/dtb/amlogic/kvim-5.dtb.overlay.env"
OVERLAY_DIR="/boot/dtb/amlogic/kvim-5.dtb.overlays"
EXT_BOARD_CODEC_OVERLAY="ext-board-codec"
EXT_BOARD_SPI_LCD_OVERLAY="spi1-lcd"
ANALOG_MIC_DEVICE="hw:0,1"
MIC_ARRAY_DEVICE="hw:0,3"

usage() {
  cat <<USAGE
Usage:
  $0 led status
  $0 led brightness <value>
  $0 fan <on|auto|off|low|mid|high|temp|trig|mode>
  $0 adc status
  $0 adc read <0|1|3>
  $0 adc aread <0|1|3|19|20>
  $0 gpio readall
  $0 gpio map
  $0 gpio in <pin>
  $0 gpio out <pin> <0|1>
  $0 pwm status
  $0 pwm write <pin> <value>
  $0 i2c status <bus>
  $0 i2c list
  $0 i2c detect <bus>
  $0 i2c read <bus> <addr> <reg> [length]
  $0 i2c write <bus> <addr> <reg> <value>
  $0 i2c write-bytes <bus> <addr> <byte> [byte...]
  $0 i2c oled-demo [bus] [addr]
  $0 spi status
  $0 spi transfer [device] [mode] [speed] <byte> [byte...]
  $0 uart status
  $0 uart send [device] [baud] <text>
  $0 uart receive [device] [baud] [timeout]
  $0 uart loopback [device] [baud] [text]
  $0 key status
  $0 key wait [timeout]
  $0 key listen
  $0 gsensor status
  $0 gsensor sample [timeout]
  $0 gsensor listen [count]
  $0 ext-board status
  $0 ext-board green-led status
  $0 ext-board green-led brightness <value>
  $0 ext-board analog-mic status
  $0 ext-board analog-mic configure
  $0 ext-board analog-mic record [seconds] [output.wav]
  $0 ext-board mic-array status
  $0 ext-board mic-array record [seconds] [output.wav]
  $0 ext-board spi-lcd status
  $0 ext-board spi-lcd test
  $0 ext-board spi-lcd clear [color]
  $0 ext-board spi-lcd text <line> [line...]
USAGE
}

install_hint_for_cmd() {
  case "$1" in
    python3)
      echo "install with: sudo apt install python3"
      ;;
    gpio)
      echo "install the Khadas/wiringpi package for VIM 5 first; on images with an apt package, try: sudo apt install wiringpi"
      ;;
    i2cdetect)
      echo "install with: sudo apt install i2c-tools"
      ;;
    amixer|arecord)
      echo "install with: sudo apt install alsa-utils"
      ;;
    gpioset|gpiofind)
      echo "install with: sudo apt install gpiod"
      ;;
    *)
      return 1
      ;;
  esac
}

need_cmd() {
  local cmd
  local hint
  cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    return 0
  fi
  echo "missing command: $cmd" >&2
  if hint="$(install_hint_for_cmd "$cmd")"; then
    echo "$hint" >&2
  fi
  exit 1
}

print_command_status() {
  local cmd
  local hint
  cmd="$1"
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "command_${cmd}=present:$(command -v "$cmd")"
  else
    echo "command_${cmd}=missing"
    if hint="$(install_hint_for_cmd "$cmd")"; then
      echo "command_${cmd}_install_hint=$hint"
    fi
  fi
}

apt_package_installed() {
  local package
  package="$1"
  command -v dpkg-query >/dev/null 2>&1 || return 1
  [ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" = "install ok installed" ]
}

python_executable() {
  need_cmd python3
  python3 -c "import sys; print(sys.executable)"
}

python_module_present() {
  local module
  module="$1"
  need_cmd python3
  python3 -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('$module') else 1)"
}

need_python_module() {
  local module
  local package
  module="$1"
  package="$2"
  if python_module_present "$module"; then
    return 0
  fi
  echo "missing Python module: $module" >&2
  if apt_package_installed "$package"; then
    echo "$package is installed for the system Python, but active Python $(python_executable) cannot import $module" >&2
    echo "run with /usr/bin/python3, deactivate Conda/base, or install the module into this Python environment" >&2
  else
    echo "install with: sudo apt install $package" >&2
  fi
  exit 1
}

need_spi_lcd_dependencies() {
  need_cmd python3
  need_python_module spidev python3-spidev
  if python_module_present gpiod || command -v gpioset >/dev/null 2>&1; then
    return 0
  fi
  echo "missing GPIO dependency for SPI LCD: need Python module gpiod or command gpioset" >&2
  if apt_package_installed gpiod || apt_package_installed python3-libgpiod; then
    echo "gpiod/python3-libgpiod appears installed for the system environment, but active Python $(python_executable) cannot import gpiod and gpioset is not in PATH" >&2
    echo "run with /usr/bin/python3, deactivate Conda/base, or fix PATH/Python environment" >&2
  else
    echo "install with: sudo apt install gpiod python3-libgpiod" >&2
  fi
  exit 1
}

repo_relative_path() {
  path="$1"
  case "$path" in
    "$REPO_ROOT"/*) echo "${path#"$REPO_ROOT"/}" ;;
    *) echo "$path" ;;
  esac
}

validate_positive_seconds() {
  seconds="$1"
  case "$seconds" in
    ''|*[!0-9]*) echo "duration seconds must be a positive integer" >&2; exit 1 ;;
  esac
  if [ "$seconds" -le 0 ]; then
    echo "duration seconds must be a positive integer" >&2
    exit 1
  fi
}

led_status_for_path() {
  label="$1"
  path="$2"
  echo "led=$label"
  echo "path=$path"
  if [ ! -d "$path" ]; then
    echo "led_ready=no"
    echo "note=missing LED path: $path"
    return 0
  fi
  echo "led_ready=yes"
  if [ -r "$path/brightness" ]; then
    echo -n "brightness="
    cat "$path/brightness"
  else
    echo "brightness=unreadable"
  fi
  if [ -r "$path/max_brightness" ]; then
    echo -n "max_brightness="
    cat "$path/max_brightness"
  else
    echo "max_brightness=unreadable"
  fi
}

set_led_brightness_for_path() {
  path="$1"
  value="$2"
  test -d "$path" || { echo "missing LED path: $path" >&2; exit 1; }
  case "$value" in
    ''|*[!0-9]*) echo "brightness must be a non-negative integer" >&2; exit 1 ;;
  esac
  max_brightness="$(cat "$path/max_brightness")"
  case "$max_brightness" in
    ''|*[!0-9]*) echo "invalid max_brightness: $max_brightness" >&2; exit 1 ;;
  esac
  if [ "$value" -gt "$max_brightness" ]; then
    echo "brightness must be 0..$max_brightness" >&2
    exit 1
  fi
  echo "$value" | sudo tee "$path/brightness" >/dev/null
}

adc_iio_channel_for_channel() {
  case "$1" in
    0) echo "0" ;;
    1|3) echo "3" ;;
    *) return 1 ;;
  esac
}

adc_input_path_for_channel() {
  iio_channel="$(adc_iio_channel_for_channel "$1")" || return 1
  echo "$IIO_DEVICE/in_voltage${iio_channel}_input"
}

adc_header_pin_for_channel() {
  case "$1" in
    0) echo "PIN10/ADC0" ;;
    1|3) echo "PIN12/ADC1" ;;
    *) return 1 ;;
  esac
}

adc_wpi_pin_for_channel() {
  case "$1" in
    0) echo "19" ;;
    1|3) echo "20" ;;
    *) return 1 ;;
  esac
}

adc_wpi_pin_for_aread_arg() {
  case "$1" in
    0|19) echo "19" ;;
    1|3|20) echo "20" ;;
    *) return 1 ;;
  esac
}

adc_header_pin_for_aread_arg() {
  case "$1" in
    0|19) echo "PIN10/ADC0" ;;
    1|3|20) echo "PIN12/ADC1" ;;
    *) return 1 ;;
  esac
}

adc_status() {
  echo "iio_device=$IIO_DEVICE"
  echo "voltage_range=0..1.8V"
  for channel in 0 1; do
    pin="$(adc_header_pin_for_channel "$channel")"
    path="$(adc_input_path_for_channel "$channel")"
    iio_channel="$(adc_iio_channel_for_channel "$channel")"
    wpi_pin="$(adc_wpi_pin_for_channel "$channel")"
    echo "channel=$channel"
    echo "header_pin=$pin"
    echo "iio_channel=$iio_channel"
    echo "input_path=$path"
    echo "wpi_pin=$wpi_pin"
    echo "wiringpi_command=gpio aread $wpi_pin"
    if [ -r "$path" ]; then
      echo "adc_ready=yes"
      echo -n "input="
      cat "$path"
    else
      echo "adc_ready=no"
      echo "note=missing or unreadable $path"
    fi
  done
}

adc_read() {
  channel="$1"
  if ! path="$(adc_input_path_for_channel "$channel")"; then
    echo "adc channel must be 0, 1, or 3" >&2
    exit 1
  fi
  pin="$(adc_header_pin_for_channel "$channel")"
  iio_channel="$(adc_iio_channel_for_channel "$channel")"
  wpi_pin="$(adc_wpi_pin_for_channel "$channel")"
  if [ ! -r "$path" ]; then
    echo "missing or unreadable ADC input node: $path" >&2
    exit 1
  fi
  echo "channel=$channel"
  echo "header_pin=$pin"
  echo "iio_channel=$iio_channel"
  echo "wpi_pin=$wpi_pin"
  echo "wiringpi_command=gpio aread $wpi_pin"
  echo "voltage_range=0..1.8V"
  echo "input_path=$path"
  echo -n "input="
  cat "$path"
}

adc_aread() {
  value="$1"
  if ! wpi_pin="$(adc_wpi_pin_for_aread_arg "$value")"; then
    echo "adc aread argument must be 0, 1, 3, 19, or 20" >&2
    exit 1
  fi
  pin="$(adc_header_pin_for_aread_arg "$value")"
  need_cmd gpio
  echo "header_pin=$pin"
  echo "wpi_pin=$wpi_pin"
  echo "wiringpi_command=gpio aread $wpi_pin"
  echo -n "input="
  gpio aread "$wpi_pin"
}

i2c_overlay_for_bus() {
  case "$1" in
    3) echo "i2c_d" ;;
    6) echo "i2c_g" ;;
    *) return 1 ;;
  esac
}

i2c_header_pins_for_bus() {
  case "$1" in
    3) echo "PIN22/PIN23" ;;
    6) echo "PIN25/PIN26" ;;
    *) return 1 ;;
  esac
}

i2c_status() {
  bus="$1"
  echo "bus=$bus"
  if overlay="$(i2c_overlay_for_bus "$bus")"; then
    pins="$(i2c_header_pins_for_bus "$bus")"
    echo "header_pins=$pins"
    echo "required_overlay=$overlay"
    echo "overlay_config=$OVERLAY_CONFIG"
    echo "overlay_dir=$OVERLAY_DIR"
  else
    echo "header_pins=unknown"
  fi

  if [ -e "/dev/i2c-$bus" ]; then
    echo "device_node=present:/dev/i2c-$bus"
    echo "i2c_ready=yes"
  else
    echo "device_node=missing:/dev/i2c-$bus"
    echo "i2c_ready=no"
    if overlay="$(i2c_overlay_for_bus "$bus")"; then
      pins="$(i2c_header_pins_for_bus "$bus")"
      echo "note=$pins are not active as I2C$bus until fdt_overlays includes $overlay in $OVERLAY_CONFIG and the system reboots"
    fi
  fi
}

warn_i2c_node() {
  bus="$1"
  if [ ! -e "/dev/i2c-$bus" ]; then
    if overlay="$(i2c_overlay_for_bus "$bus")"; then
      pins="$(i2c_header_pins_for_bus "$bus")"
      echo "warning: missing /dev/i2c-$bus; I2C$bus on $pins is unavailable until fdt_overlays includes $overlay in $OVERLAY_CONFIG and the system reboots" >&2
    else
      echo "warning: missing /dev/i2c-$bus" >&2
    fi
  fi
}

spi_status() {
  echo "spi=SPI1"
  echo "header_pins=PIN25/PIN26/PIN36/PIN37"
  echo "required_overlay=$SPI_OVERLAY"
  echo "overlay_config=$OVERLAY_CONFIG"
  echo "overlay_dir=$OVERLAY_DIR"
  echo "device_node=$SPI_DEVICE"
  echo "shared_pins=PIN25/PIN26 are shared with I2C6"
  if [ -e "$SPI_DEVICE" ]; then
    echo "spi_ready=yes"
  else
    echo "spi_ready=no"
    echo "note=PIN25/PIN26/PIN36/PIN37 are not active as SPI1 until fdt_overlays includes $SPI_OVERLAY and the system reboots"
  fi
}

warn_spi_node() {
  device="${1:-$SPI_DEVICE}"
  if [ ! -e "$device" ]; then
    if [ "$device" = "$SPI_DEVICE" ]; then
      echo "warning: missing $SPI_DEVICE; SPI1 on PIN25/PIN26/PIN36/PIN37 is unavailable until fdt_overlays includes $SPI_OVERLAY and the system reboots" >&2
    else
      echo "warning: missing $device" >&2
    fi
  fi
}

parse_spi_transfer_args() {
  case "$#" in
    0)
      echo "spi transfer requires at least one byte" >&2
      exit 1
      ;;
  esac

  SPI_ARG_DEVICE="$SPI_DEVICE"
  SPI_ARG_MODE="0"
  SPI_ARG_SPEED="500000"
  SPI_ARG_DATA=()

  case "${1:-}" in
    /dev/*)
      SPI_ARG_DEVICE="$1"
      shift
      ;;
  esac

  if [ "$#" -ge 2 ] && expr "$1" : '^[0-3]$' >/dev/null && expr "$2" : '^[0-9][0-9]*$' >/dev/null; then
    SPI_ARG_MODE="$1"
    SPI_ARG_SPEED="$2"
    shift 2
  fi

  if [ "$#" -eq 0 ]; then
    echo "spi transfer requires at least one byte" >&2
    exit 1
  fi
  SPI_ARG_DATA=("$@")
}

uart_status() {
  echo "uart=UART_AO_E"
  echo "header_pins=PIN15(RX)/PIN16(TX)"
  echo "required_overlay=$UART_OVERLAY"
  echo "overlay_config=$OVERLAY_CONFIG"
  echo "overlay_dir=$OVERLAY_DIR"
  echo "device_node=$UART_DEVICE"
  if [ -e "$UART_DEVICE" ]; then
    echo "uart_ready=yes"
  else
    echo "uart_ready=no"
    echo "note=PIN15/PIN16 are not active as UART until fdt_overlays includes $UART_OVERLAY and the system reboots"
  fi
}

warn_uart_node() {
  device="${1:-$UART_DEVICE}"
  if [ ! -e "$device" ]; then
    if [ "$device" = "$UART_DEVICE" ]; then
      echo "warning: missing $UART_DEVICE; UART on PIN15/PIN16 is unavailable until fdt_overlays includes $UART_OVERLAY and the system reboots" >&2
    else
      echo "warning: missing $device" >&2
    fi
  fi
}

key_status() {
  echo "key=FUNC"
  echo "device=$KEY_DEVICE"
  echo "expected_name=$KEY_NAME"
  if [ -e "$KEY_DEVICE" ]; then
    echo "device_node=present:$KEY_DEVICE"
  else
    echo "device_node=missing:$KEY_DEVICE"
    echo "key_ready=no"
    echo "note=VIM 5 Func key is expected at $KEY_DEVICE as $KEY_NAME"
    return 1
  fi
}

gsensor_status() {
  echo "accelerometer=G-sensor"
  echo "device=$GSENSOR_DEVICE"
  echo "expected_name=$GSENSOR_NAME"
  echo "axis_codes=x:ABS_X(0),y:ABS_Y(1),z:ABS_Z(2)"
  echo "axis_orientation_reference=top_view_USB-A_edge_at_top_HDMI_IN_edge_at_bottom_Gsensor_near_left_edge"
  echo "axis_x_positive=USB-A_edge"
  echo "axis_x_negative=HDMI_IN_edge"
  echo "axis_y_positive=left_Gsensor_edge"
  echo "axis_y_negative=right_USB-A_2_0_edge"
  echo "axis_z_positive=component_side_up"
  echo "axis_z_negative=board_back_side"
  echo "units=raw input-event values"
  if [ -e "$GSENSOR_DEVICE" ]; then
    echo "device_node=present:$GSENSOR_DEVICE"
  else
    echo "device_node=missing:$GSENSOR_DEVICE"
    echo "gsensor_ready=no"
    echo "note=VIM 5 G-sensor is expected at $GSENSOR_DEVICE as $GSENSOR_NAME"
    return 1
  fi
}

ext_board_analog_mic_status() {
  echo "analog_mic=extension_board_codec"
  echo "required_overlay=$EXT_BOARD_CODEC_OVERLAY"
  echo "overlay_config=$OVERLAY_CONFIG"
  echo "overlay_dir=$OVERLAY_DIR"
  echo "capture_device=$ANALOG_MIC_DEVICE"
  echo "configure_command=amixer -c 0 cset name='TDMIN_B source select' 'tdmin_b'"
  echo "record_command=arecord -D hw:0,1 -f cd -c 2 -d 10 test.wav"
  echo "pin_conflict=ext-board-codec shares pins with i2s and spi; avoid conflicting overlays at the same time"
  print_command_status amixer
  print_command_status arecord
}

ext_board_mic_array_status() {
  echo "mic_array=onboard_pdm_array"
  echo "capture_device=$MIC_ARRAY_DEVICE"
  echo "record_command=arecord -Dhw:0,3 -r 48000 -f S16_LE -c 6 -d 10 pdm_6ch.wav"
  print_command_status arecord
}

ext_board_spi_lcd_status() {
  echo "spi_lcd=three_wire_spi_oled"
  echo "required_overlay=$EXT_BOARD_SPI_LCD_OVERLAY"
  echo "overlay_config=$OVERLAY_CONFIG"
  echo "overlay_dir=$OVERLAY_DIR"
  echo "device_node=$SPI_DEVICE"
  echo "control_script=$(repo_relative_path "$SPI_LCD_HELPER")"
  echo "apt_dependencies=python3-spidev gpiod python3-libgpiod"
  echo "pin_conflict=spi1-lcd uses SPI pins; avoid conflicting ext-board-codec, i2s, or spi overlays at the same time"
  if [ -e "$SPI_DEVICE" ]; then
    echo "device_node_ready=yes"
  else
    echo "device_node_ready=no"
    echo "note=missing $SPI_DEVICE; enable $EXT_BOARD_SPI_LCD_OVERLAY in fdt_overlays and reboot"
  fi
  if [ -f "$SPI_LCD_HELPER" ]; then
    echo "control_script_ready=yes"
    need_cmd python3
    python3 "$SPI_LCD_HELPER" status
  else
    echo "control_script_ready=no"
  fi
}

ext_board_status() {
  echo "expansion_board=VIM 5 extension board"
  echo "overlay_config=$OVERLAY_CONFIG"
  echo "overlay_dir=$OVERLAY_DIR"
  led_status_for_path "green_led" "$EXT_GREEN_LED_PATH"
  ext_board_analog_mic_status
  ext_board_mic_array_status
  ext_board_spi_lcd_status
}

ext_board_analog_mic_configure() {
  need_cmd amixer
  echo "note=$EXT_BOARD_CODEC_OVERLAY must be active after reboot before analog MIC capture is available" >&2
  amixer -c 0 cset "name=TDMIN_B source select" "tdmin_b"
}

ext_board_analog_mic_record() {
  seconds="${1:-10}"
  output="${2:-test.wav}"
  validate_positive_seconds "$seconds"
  need_cmd arecord
  echo "note=$EXT_BOARD_CODEC_OVERLAY must be active after reboot before analog MIC capture is available" >&2
  arecord -D "$ANALOG_MIC_DEVICE" -f cd -c 2 -d "$seconds" "$output"
}

ext_board_mic_array_record() {
  seconds="${1:-10}"
  output="${2:-pdm_6ch.wav}"
  validate_positive_seconds "$seconds"
  need_cmd arecord
  arecord -D "$MIC_ARRAY_DEVICE" -r 48000 -f S16_LE -c 6 -d "$seconds" "$output"
}

parse_uart_send_args() {
  case "$#" in
    1)
      UART_ARG_DEVICE="$UART_DEVICE"
      UART_ARG_BAUD="115200"
      UART_ARG_TEXT="$1"
      ;;
    2)
      if expr "$1" : '^[0-9][0-9]*$' >/dev/null; then
        UART_ARG_DEVICE="$UART_DEVICE"
        UART_ARG_BAUD="$1"
        UART_ARG_TEXT="$2"
      else
        UART_ARG_DEVICE="$1"
        UART_ARG_BAUD="115200"
        UART_ARG_TEXT="$2"
      fi
      ;;
    3)
      UART_ARG_DEVICE="$1"
      UART_ARG_BAUD="$2"
      UART_ARG_TEXT="$3"
      ;;
    *)
      echo "uart send requires <text>, [baud] <text>, [device] <text>, or [device] [baud] <text>" >&2
      exit 1
      ;;
  esac
}

parse_uart_loopback_args() {
  case "$#" in
    0)
      UART_ARG_DEVICE="$UART_DEVICE"
      UART_ARG_BAUD="115200"
      UART_ARG_TEXT="hello"
      ;;
    1|2|3)
      parse_uart_send_args "$@"
      ;;
    *)
      echo "uart loopback accepts [text], [baud] [text], [device] [text], or [device] [baud] [text]" >&2
      exit 1
      ;;
  esac
}

gpio_default_map() {
  cat <<'MAP'
Default Khadas VIM 5 40-pin GPIO map from gpio readall.
Use the wPi column with wiringpi commands such as gpio mode/read/write.

Physical  wPi  GPIO  Name       Mode  V  Pull   Notes
13        1    641   PIN.D13    IN    0  P/D    GPIO by default; SPDIF when spdifout is active
15        2    637   PIN.D9     IN    0  P/U    GPIO by default; UART RX when uart_ao_e is active
16        3    636   PIN.D8     IN    0  P/D    GPIO by default; UART TX when uart_ao_e is active
18        4    629   PIN.D1     ALT0  1  P/U    Alternate function by default
19        5    628   PIN.D0     ALT0  1  P/U    Alternate function by default
22        6    591   PIN.A15    IN    1  P/D    GPIO by default; I2C3 when i2c_d is active
23        7    590   PIN.A14    IN    1  P/D    GPIO by default; I2C3 when i2c_d is active
25        8    555   PIN.M1     IN    1  P/D    GPIO by default; I2C6 when i2c_g is active; shared with SPI1
26        9    554   PIN.M0     IN    1  P/D    GPIO by default; I2C6 when i2c_g is active; shared with SPI1
29        10   577   PIN.A1     IN    0  P/D    GPIO input by default
30        11   576   PIN.A0     IN    0  P/D    GPIO input by default
31        12   579   PIN.A3     IN    0  P/D    GPIO input by default
32        13   578   PIN.A2     IN    0  P/D    GPIO input by default
33        14   580   PIN.A4     IN    0  P/D    GPIO input by default
35        15   601   PIN.Y5     IN    1  P/U    GPIO by default; PWM when pwm_j is active
36        16   556   PIN.M2     IN    1  P/D    GPIO by default; SPI1 when spi1 is active
37        17   557   PIN.M3     IN    1  P/D    GPIO by default; SPI1 when spi1 is active
39        18   633   PIN.D5     IN    1  P/U    GPIO by default; IR when ir is active

ADC-only entries:
ADC voltage range: 0..1.8V
Physical  wPi  Name     Input node                                             wiringpi ADC command
10        19   ADC0     /sys/bus/iio/devices/iio:device0/in_voltage0_input  gpio aread 19
12        20   ADC1     /sys/bus/iio/devices/iio:device0/in_voltage3_input  gpio aread 20

Non-GPIO/reserved/power pins:
1,2=5V  20,27=3V3  5,9,14,17,21,24,28,34,40=GND  11=1.8V
6=MCU3.3  3,4=USB_DM/USB_DP  7=MCUNRST  8=MCUSWIM  38=PWR_HOLD
MAP
}

case "${1:-}" in
  adc)
    case "${2:-}" in
      status)
        adc_status
        ;;
      read)
        adc_read "${3:?channel required}"
        ;;
      aread)
        adc_aread "${3:?channel or wPi pin required}"
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  led)
    case "${2:-}" in
      status)
        led_status_for_path "pwmled" "$LED_PATH"
        ;;
      brightness)
        value="${3:?brightness value required}"
        set_led_brightness_for_path "$LED_PATH" "$value"
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  fan)
    action="${2:-}"
    case "$action" in
      on|auto|off|low|mid|high|temp|trig|mode)
        test -x "$FAN_SCRIPT" || { echo "missing fan script: $FAN_SCRIPT" >&2; exit 1; }
        "$FAN_SCRIPT" "$action"
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  gpio)
    case "${2:-}" in
      readall)
        need_cmd gpio
        gpio readall
        ;;
      map) gpio_default_map ;;
      in)
        need_cmd gpio
        pin="${3:?pin required}"
        gpio mode "$pin" in
        gpio read "$pin"
        ;;
      out)
        need_cmd gpio
        pin="${3:?pin required}"
        value="${4:?0 or 1 required}"
        case "$value" in
          0|1) ;;
          *) echo "gpio value must be 0 or 1" >&2; exit 1 ;;
        esac
        gpio mode "$pin" out
        gpio write "$pin" "$value"
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  pwm)
    case "${2:-}" in
      status)
        echo "pwm=PWM_J"
        echo "header_pin=PIN35"
        echo "wPi=15"
        echo "gpio=601"
        echo "required_overlay=pwm_j"
        echo "note=PIN35 is GPIO by default until fdt_overlays includes pwm_j and the system reboots"
        ;;
      write)
        need_cmd gpio
        pin="${3:?pin required}"
        value="${4:?pwm value required}"
        case "$value" in
          ''|*[!0-9]*) echo "pwm value must be a non-negative integer" >&2; exit 1 ;;
        esac
        gpio mode "$pin" pwm
        gpio pwm "$pin" "$value"
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  i2c)
    case "${2:-}" in
      status)
        bus="${3:?bus required}"
        i2c_status "$bus"
        ;;
      list)
        need_cmd i2cdetect
        i2cdetect -l
        ;;
      detect)
        need_cmd i2cdetect
        bus="${3:?bus required}"
        warn_i2c_node "$bus"
        i2cdetect -y "$bus"
        ;;
      read)
        need_cmd python3
        test -f "$I2C_HELPER" || { echo "missing i2c helper: $I2C_HELPER" >&2; exit 1; }
        warn_i2c_node "${3:?bus required}"
        python3 "$I2C_HELPER" read \
          --bus "$3" \
          --addr "${4:?addr required}" \
          --reg "${5:?reg required}" \
          --length "${6:-1}"
        ;;
      write)
        need_cmd python3
        test -f "$I2C_HELPER" || { echo "missing i2c helper: $I2C_HELPER" >&2; exit 1; }
        warn_i2c_node "${3:?bus required}"
        python3 "$I2C_HELPER" write \
          --bus "$3" \
          --addr "${4:?addr required}" \
          --reg "${5:?reg required}" \
          --value "${6:?value required}"
        ;;
      write-bytes)
        need_cmd python3
        test -f "$I2C_HELPER" || { echo "missing i2c helper: $I2C_HELPER" >&2; exit 1; }
        bus="${3:?bus required}"
        addr="${4:?addr required}"
        warn_i2c_node "$bus"
        shift 4
        if [ "$#" -eq 0 ]; then
          echo "at least one byte is required" >&2
          exit 1
        fi
        python3 "$I2C_HELPER" write-bytes --bus "$bus" --addr "$addr" --data "$@"
        ;;
      oled-demo)
        need_cmd python3
        test -f "$OLED_HELPER" || { echo "missing oled helper: $OLED_HELPER" >&2; exit 1; }
        bus="${3:-3}"
        warn_i2c_node "$bus"
        python3 "$OLED_HELPER" --bus "$bus" --addr "${4:-0x3c}"
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  spi)
    case "${2:-}" in
      status)
        spi_status
        ;;
      transfer)
        need_cmd python3
        test -f "$SPI_HELPER" || { echo "missing spi helper: $SPI_HELPER" >&2; exit 1; }
        shift 2
        parse_spi_transfer_args "$@"
        warn_spi_node "$SPI_ARG_DEVICE"
        python3 "$SPI_HELPER" transfer \
          --device "$SPI_ARG_DEVICE" \
          --mode "$SPI_ARG_MODE" \
          --speed "$SPI_ARG_SPEED" \
          --data "${SPI_ARG_DATA[@]}"
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  uart)
    case "${2:-}" in
      status)
        uart_status
        ;;
      send)
        need_cmd python3
        test -f "$UART_HELPER" || { echo "missing uart helper: $UART_HELPER" >&2; exit 1; }
        shift 2
        parse_uart_send_args "$@"
        warn_uart_node "$UART_ARG_DEVICE"
        python3 "$UART_HELPER" send --device "$UART_ARG_DEVICE" --baud "$UART_ARG_BAUD" --text "$UART_ARG_TEXT"
        ;;
      receive)
        need_cmd python3
        test -f "$UART_HELPER" || { echo "missing uart helper: $UART_HELPER" >&2; exit 1; }
        device="${3:-$UART_DEVICE}"
        baud="${4:-115200}"
        timeout="${5:-5}"
        warn_uart_node "$device"
        python3 "$UART_HELPER" receive --device "$device" --baud "$baud" --timeout "$timeout"
        ;;
      loopback)
        need_cmd python3
        test -f "$UART_HELPER" || { echo "missing uart helper: $UART_HELPER" >&2; exit 1; }
        shift 2
        parse_uart_loopback_args "$@"
        warn_uart_node "$UART_ARG_DEVICE"
        python3 "$UART_HELPER" loopback --device "$UART_ARG_DEVICE" --baud "$UART_ARG_BAUD" --text "$UART_ARG_TEXT"
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  key)
    case "${2:-}" in
      status)
        key_status
        need_cmd python3
        test -f "$KEY_HELPER" || { echo "missing key helper: $KEY_HELPER" >&2; exit 1; }
        python3 "$KEY_HELPER" status
        ;;
      wait)
        need_cmd python3
        test -f "$KEY_HELPER" || { echo "missing key helper: $KEY_HELPER" >&2; exit 1; }
        timeout="${3:-10}"
        python3 "$KEY_HELPER" wait --timeout "$timeout"
        ;;
      listen)
        need_cmd python3
        test -f "$KEY_HELPER" || { echo "missing key helper: $KEY_HELPER" >&2; exit 1; }
        python3 "$KEY_HELPER" listen
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  gsensor|g-sensor|accel|accelerometer)
    case "${2:-}" in
      status)
        gsensor_status
        need_cmd python3
        test -f "$GSENSOR_HELPER" || { echo "missing G-sensor helper: $GSENSOR_HELPER" >&2; exit 1; }
        python3 "$GSENSOR_HELPER" status
        ;;
      sample)
        need_cmd python3
        test -f "$GSENSOR_HELPER" || { echo "missing G-sensor helper: $GSENSOR_HELPER" >&2; exit 1; }
        timeout="${3:-5}"
        python3 "$GSENSOR_HELPER" sample --timeout "$timeout"
        ;;
      listen)
        need_cmd python3
        test -f "$GSENSOR_HELPER" || { echo "missing G-sensor helper: $GSENSOR_HELPER" >&2; exit 1; }
        if [ -n "${3:-}" ]; then
          python3 "$GSENSOR_HELPER" listen --count "$3"
        else
          python3 "$GSENSOR_HELPER" listen
        fi
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  ext-board)
    case "${2:-}" in
      status)
        ext_board_status
        ;;
      green-led|led)
        case "${3:-}" in
          status)
            led_status_for_path "green_led" "$EXT_GREEN_LED_PATH"
            ;;
          brightness)
            value="${4:?brightness value required}"
            set_led_brightness_for_path "$EXT_GREEN_LED_PATH" "$value"
            ;;
          *) usage; exit 1 ;;
        esac
        ;;
      analog-mic)
        case "${3:-}" in
          status)
            ext_board_analog_mic_status
            ;;
          configure)
            ext_board_analog_mic_configure
            ;;
          record)
            ext_board_analog_mic_record "${4:-10}" "${5:-test.wav}"
            ;;
          *) usage; exit 1 ;;
        esac
        ;;
      mic-array)
        case "${3:-}" in
          status)
            ext_board_mic_array_status
            ;;
          record)
            ext_board_mic_array_record "${4:-10}" "${5:-pdm_6ch.wav}"
            ;;
          *) usage; exit 1 ;;
        esac
        ;;
      spi-lcd|oled)
        case "${3:-}" in
          status)
            ext_board_spi_lcd_status
            ;;
          test)
            need_spi_lcd_dependencies
            test -f "$SPI_LCD_HELPER" || { echo "missing SPI LCD helper: $SPI_LCD_HELPER" >&2; exit 1; }
            python3 "$SPI_LCD_HELPER" test
            ;;
          clear)
            need_spi_lcd_dependencies
            test -f "$SPI_LCD_HELPER" || { echo "missing SPI LCD helper: $SPI_LCD_HELPER" >&2; exit 1; }
            python3 "$SPI_LCD_HELPER" clear --color "${4:-black}"
            ;;
          text)
            need_spi_lcd_dependencies
            test -f "$SPI_LCD_HELPER" || { echo "missing SPI LCD helper: $SPI_LCD_HELPER" >&2; exit 1; }
            shift 3
            if [ "$#" -eq 0 ]; then
              echo "at least one text line is required" >&2
              exit 1
            fi
            lcd_text_args=()
            for line in "$@"; do
              lcd_text_args+=(--line "$line")
            done
            python3 "$SPI_LCD_HELPER" text "${lcd_text_args[@]}"
            ;;
          *) usage; exit 1 ;;
        esac
        ;;
      *) usage; exit 1 ;;
    esac
    ;;
  *) usage; exit 1 ;;
esac
