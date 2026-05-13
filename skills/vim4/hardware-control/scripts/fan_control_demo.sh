#!/usr/bin/env bash
set -euo pipefail

FAN_SCRIPT="${FAN_SCRIPT:-/usr/local/bin/fan.sh}"

usage() {
  cat <<USAGE
Usage:
  $0 status
  $0 <on|auto|off|low|mid|high>
  $0 cycle [seconds_per_level]
  $0 watch [interval_seconds] [sample_count]

Examples:
  $0 status
  $0 high
  $0 auto
  $0 cycle 3
  $0 watch 2 10

Notes:
  This demo controls the VIM4 fan through $FAN_SCRIPT.
  The cycle command runs low -> mid -> high, then returns to auto mode.
USAGE
}

die() {
  echo "error: $*" >&2
  exit 1
}

require_fan_script() {
  if [ ! -x "$FAN_SCRIPT" ]; then
    die "missing executable fan helper: $FAN_SCRIPT"
  fi
}

require_positive_int() {
  name="$1"
  value="$2"
  case "$value" in
    ''|*[!0-9]*) die "$name must be a positive integer" ;;
  esac
  if [ "$value" -le 0 ]; then
    die "$name must be greater than 0"
  fi
}

fan() {
  "$FAN_SCRIPT" "$1"
}

status() {
  echo "fan_mode:"
  fan mode
  echo
  echo "fan_trigger:"
  fan trig
  echo
  echo "cpu_temperature:"
  fan temp
}

set_fan() {
  action="$1"
  fan "$action"
  echo
  status
}

cycle_demo() {
  seconds="${1:-2}"
  require_positive_int "seconds_per_level" "$seconds"

  echo "starting fan cycle demo: low -> mid -> high -> auto"
  for level in low mid high; do
    echo
    echo "setting fan level: $level"
    fan "$level"
    sleep "$seconds"
    status
  done

  echo
  echo "returning fan to auto mode"
  fan auto
  echo
  status
}

watch_status() {
  interval="${1:-2}"
  samples="${2:-10}"
  require_positive_int "interval_seconds" "$interval"
  require_positive_int "sample_count" "$samples"

  index=1
  while [ "$index" -le "$samples" ]; do
    echo "sample=$index"
    status
    if [ "$index" -lt "$samples" ]; then
      echo
      sleep "$interval"
    fi
    index=$((index + 1))
  done
}

main() {
  case "${1:-}" in
    -h|--help|help|'')
      usage
      ;;
    status)
      require_fan_script
      status
      ;;
    on|auto|off|low|mid|high)
      require_fan_script
      set_fan "$1"
      ;;
    cycle)
      require_fan_script
      cycle_demo "${2:-2}"
      ;;
    watch)
      require_fan_script
      watch_status "${2:-2}" "${3:-10}"
      ;;
    *)
      usage >&2
      exit 1
      ;;
  esac
}

main "$@"
