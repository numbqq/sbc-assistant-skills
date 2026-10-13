#!/usr/bin/env bash
set -euo pipefail
asr_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export LD_LIBRARY_PATH="$asr_root/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$asr_root/bin/asr_realtime" --model-dir "$asr_root/model/" "$@"
