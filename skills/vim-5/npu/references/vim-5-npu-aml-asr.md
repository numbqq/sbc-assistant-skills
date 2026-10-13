# AML ASR on VIM 5

Use the installed skill's `assets/aml-asr` runtime for Amlogic AAI SDK 3.1.2
microphone transcription with approximately one-second incremental previews
and finalized results after a silence boundary. Keep Whisper available when
its model/language behavior is preferred; only one engine may own the same
ALSA capture device at a time.

## Prepare installed assets

```bash
sudo apt-get install alsa-utils
# Run from the skill registry repository; assembly is automatic.
bash scripts/install.sh --tool picoclaw --skill khadas-vim-5-npu
cd "$HOME/.picoclaw/workspace/skills/khadas-vim-5-npu/assets/aml-asr"
sha256sum -c SHA256SUMS.txt
bash run.sh --protocol-version
LD_LIBRARY_PATH="$PWD/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" ldd bin/asr_realtime
```

The ten model parts total about 455 MiB. Assembly needs another 455 MiB,
verifies their SHA-256 and the complete model, and refuses to replace a corrupt
existing model. Move the bad generated `.nb` aside, then retry. Installed
assets remain independent of `~/aml-asr`. Debian 12 ARM64 requires the board's
matching libnnsdk/NPU runtime and an accessible `/dev/adla0`; any `not found`
library prevents startup. No Conda environment or OpenCC is required for AML
ASR itself. The installer assembles and verifies the model automatically on
installation/reinstallation before replacing the old directory. Failure keeps
the previous skill. Updates temporarily need space for both bundles.
Direct file copies or older installers still need `bash assemble-model.sh`;
it is also available for manual verification/recovery.

## Independent microphone test

Stop the existing Gateway/Whisper/ASR first, then run from the asset directory:

```bash
bash run.sh --device hw:0,3 --capture-rate 48000 --capture-channels 6 \
  --mic-channel 2 --language zh
```

Wait for `[ready] Listening`, then speak and pause. `[preview]` can be revised;
`[transcription]` is final. Ctrl+C releases the microphone. PDM channel 2 was
verified on the current VIM 5; channels 0/1 were almost all zero. Confirm the
mapping on other arrays. Analog `hw:0,1` needs the expansion-board overlay and
ALSA route described in the Whisper reference, and uses 44100 Hz / 2ch /
channel 0. `--language zh|en|auto`, `--step-ms 1000`, `--silence-ms 600`, and
`--speech-threshold 0.003` can be configured; see `bash run.sh --help`.

## Picoclaw configuration

In the product repository, using the matching updated configurator:

```bash
runtime/configure-picoclaw-vibe-hook --voice --asr-backend aml-asr
# Switch back after stopping the Gateway:
runtime/configure-picoclaw-vibe-hook --voice --asr-backend whisper
```

Restart one Gateway after changing configuration. Each command updates the
same `channel_list.local_voice` and preserves provider/Feishu configuration;
it selects the process command and records `settings.backend`. Do not change
only the label without its matching command. For a custom workspace/root use
`--aml-asr-root /path/to/installed/skill/assets/aml-asr`.

AML ASR writes JSONL with `--output-format jsonl`: ready, preview, transcription,
endpoint, level, error, stopped. Each final has a positive process-local
sequence, text and configured language. Picoclaw submits only final text with
letters or numbers, deduplicates sequences per process, ignores previews,
and supervises process restarts. SDK logs go to stderr. Unknown confidence
and duration remain null; do not interpret cumulative `audio_seconds` as a
sentence duration. Existing UI subtitles appear on finalization, not on every
preview, and no TTS is added.

## Fixed sample

```bash
# This bundled WAV has a verified standard 44-byte PCM header.
dd if=input/zh_16k_mono.wav of=/tmp/aml-asr-fixture.pcm bs=1 skip=44 status=none
bash run.sh --pcm-file /tmp/aml-asr-fixture.pcm --capture-rate 16000 \
  --capture-channels 1 --language zh --output-format jsonl
```

Expected final: `你好你好你好，你现在好吗？`. Sequence must be nonzero.
Raw PCM replay uses channel 0 by default; arbitrary WAVs need proper decoding
rather than assuming a 44-byte header. Passing WAV directly to `--pcm-file`
is rejected.
