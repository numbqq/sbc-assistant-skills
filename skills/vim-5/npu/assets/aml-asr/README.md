# AML ASR runtime for VIM 5

Self-contained ARM64 Linux runtime for the `khadas-vim-5-npu` skill and
Picoclaw's `local_voice` channel. Uses Amlogic AAI SDK 3.1.2 and the
`asr123_v1p3.nb` model. No Conda, Python inference packages or source checkout
are needed at runtime. The board supplies NPU drivers, libnnsdk/libadla, and
`arecord` from `alsa-utils`.

- `bin/asr_realtime`: native C++ microphone/raw PCM producer.
- `lib/`: matching vendor SDK and ONNX runtime libraries.
- `model/`: ten ordinary Git model parts (at most 50,000,000 bytes each),
  part/model SHA-256 manifests, and the assembled model after preparation.
- `input/zh_16k_mono.wav`: fixed verification sample.
- `run.sh`: sets the skill-relative library/model paths, then execs the binary.
- `assemble-model.sh`: verifies parts and assembles the model atomically.
- `SHA256SUMS.txt`: bundled binary, libraries, sample and model-part hashes.
- `SOURCE_SHA256SUMS.txt`: source hashes for the packaged binary, built from the
  `aml-asr` sources based on `c54d7c52c39be5b3694e8803850f8064bc045bdc`
  plus named ALSA PDM/analog device support; the manifest identifies the exact files.

`scripts/install.sh` automatically verifies the parts and assembles the model
when installing or reinstalling this skill. Preparation happens before the
previous installation is replaced; failure keeps the old skill and returns an
error. Assembly needs about 455 MiB additional disk space. Updates temporarily
need room for both old and new skill bundles. Direct copies or older installers
still need `bash assemble-model.sh` from this directory; it also works on a
developer host. Verify `sha256sum -c SHA256SUMS.txt` and
`(cd model && sha256sum -c MODEL_SHA256SUMS.txt)` before release.

`bash run.sh --protocol-version` must print `local-voice-jsonl-v1`. Old native
binaries without nonzero transcription sequences cannot feed Picoclaw.
Only finalized text is submitted; previews remain diagnostic events. Sequence
numbers start at 1 for each process. `language` records the configured language
(`auto` does not claim a detected language), and confidence/duration are null
because the SDK interface does not provide them. `audio_seconds` is cumulative
processed capture time, not per-utterance duration.

PDM defaults to `hw:CARD=AMLAUGESOUND,DEV=3` (48000 Hz, 6ch, channel 2).
Analog `--device hw:CARD=AMLAUGESOUND,DEV=1` selects 44100 Hz, 2ch, channel 0
and requires the `ext-board-codec` overlay plus `amixer -c AMLAUGESOUND` routing.
Named addresses do not change when USB audio changes the card numbering.

The vendor SDK/model are supplied as-is; no new open-source license is assigned
to them. SDK provenance: Linux ARM64 3.1.2, build 2026-10-10, cid a2002e8e9.
Audio conversion in the native program derives from Amlogic Whisper's
Apache-2.0 code; its notice is in `NOTICE.audio.txt`. Rebuild on a matching VIM 5
using `bash build.sh` in the `aml-asr` source repo, replace the executable,
and regenerate the binary/source manifests when source or runtime ABI changes.
