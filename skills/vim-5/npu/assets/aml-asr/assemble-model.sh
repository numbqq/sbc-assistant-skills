#!/usr/bin/env bash
# Reassemble the vendor model from ordinary Git files, then verify SHA-256.
set -euo pipefail
[[ $# -eq 0 ]] || { echo "Usage: $0" >&2; exit 2; }
asr_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd -- "$asr_root/model"
sha256sum -c PARTS_SHA256SUMS.txt
read -r asr_expected asr_model < MODEL_SHA256SUMS.txt
if [[ -f "$asr_model" ]] && sha256sum -c MODEL_SHA256SUMS.txt >/dev/null 2>&1; then
  echo "Model already assembled and verified: $asr_root/model/$asr_model"
  exit 0
fi
if [[ -e "$asr_model" ]]; then
  echo "Existing $asr_model failed SHA-256 verification. Move it aside before retrying." >&2
  exit 2
fi
asr_tmp=$(mktemp .assemble.XXXXXX)
trap 'rm -f -- "$asr_tmp"' EXIT
cat asr123_v1p3.nb.part{00..09} > "$asr_tmp"
printf '%s  %s\n' "$asr_expected" "$asr_tmp" | sha256sum -c -
mv -- "$asr_tmp" "$asr_model"
echo "Model assembled and verified: $asr_root/model/$asr_model"
