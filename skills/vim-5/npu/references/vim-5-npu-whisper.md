# VIM 5 NPU Whisper Reference

## Target and bundled files

- Board: Khadas VIM 5 (A311Y3)
- Runtime: Amlogic AMLNNLite in conda environment `amlnnlite_py310`
- NPU model format: ADLA, quantized `w8a16`
- Whisper feature rate: mono 16 kHz; the script resamples file and microphone input
- Decoder limit: 48 token positions per inference segment

```text
scripts/vim-5_whisper.py
assets/whisper/bin/whisper_demo
assets/whisper/data_bin/data.bin
assets/whisper/data_bin/tokenizer_info.bin
assets/whisper/model/whisper_encoder_static_sim_w8a16.adla
assets/whisper/model/whisper_decoder_static_sim_w8a16.adla
assets/whisper/tokenizer/
assets/whisper/LICENSE.openai.txt
```

The script first tries `amlnnlite.api.AMLNNLite` and falls back to
`amlnn.api.AMLNN`. It loads the local tokenizer with
`local_files_only=True`, so normal inference does not require network access.
The ARM64 `whisper_demo` binary and `data_bin` files provide the machine-readable
JSONL producer used by Picoclaw's `local_voice` channel. Run it with
`assets/whisper/` as its working directory so no source checkout path is needed.

## Dependencies

Check the target environment rather than system Python:

```bash
conda run -n amlnnlite_py310 python -c \
  'import amlnnlite, librosa, numpy, transformers; print("ready")'
command -v arecord
ls -l /dev/adla*
```

Install missing Python preprocessing dependencies into the same environment as
AMLNNLite:

```bash
conda run -n amlnnlite_py310 pip install librosa transformers
```

The AMLNNLite wheel is platform-specific. Do not replace it with a generic PyPI
package or run the NPU script with a different Python environment.

## Status and generated commands

Run from the installed `khadas-vim-5-npu` skill directory:

```bash
scripts/vim-5_npu_status.py status
scripts/vim-5_npu_status.py whisper-microphone-command
scripts/vim-5_npu_status.py whisper-microphone-command \
  --device hw:0,1 --capture-rate 44100 --capture-channels 2
scripts/vim-5_npu_status.py whisper-file-command --audio-file /path/to/audio.wav
```

The helper emits a `conda run` command with absolute paths to the installed
script, models, and tokenizer. For `hw:0,1`, it prefixes the command with the
required `amixer` route setup joined by `&&`, so Whisper does not start if route
configuration fails. Execute the printed command on the VIM 5 host.

## Audio-file inference

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_whisper.py \
  --enc assets/whisper/model/whisper_encoder_static_sim_w8a16.adla \
  --dec assets/whisper/model/whisper_decoder_static_sim_w8a16.adla \
  --tokenizer assets/whisper/tokenizer \
  --audio-file /path/to/audio.wav \
  --language auto
```

Files longer than 30 seconds are split into overlapping segments and merged.
Automatic language detection runs once per segment. A fixed language avoids
that extra decoder call and is usually more stable for short utterances.

## Real-time PDM Mic Array

The VIM 5 Mic Array exposes six interleaved channels and must be opened with its
hardware parameters:

```bash
arecord -D hw:0,3 -r 48000 -f S16_LE -c 6 -d 5 /tmp/pdm-6ch.wav
```

Real-time automatic-language transcription:

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_whisper.py \
  --enc assets/whisper/model/whisper_encoder_static_sim_w8a16.adla \
  --dec assets/whisper/model/whisper_decoder_static_sim_w8a16.adla \
  --tokenizer assets/whisper/tokenizer \
  --microphone \
  --device hw:0,3 \
  --capture-rate 48000 \
  --capture-channels 6 \
  --mic-channel 0 \
  --language auto
```

Channels `0` through `5` can be selected independently. `--mic-channel mix`
averages them, which can improve stationary noise but may reduce speech level if
the microphones contain phase differences. Start with channel 0, inspect all
channel levels when recognition is poor, then select the cleanest channel.

## Real-time analog MIC

`-f cd` is ALSA shorthand for S16_LE, 44100 Hz, stereo:

Analog capture has mandatory hardware prerequisites:

1. Connect the VIM 5 expansion board.
2. Set `fdt_overlays=ext-board-codec` in
   `/boot/dtb/amlogic/kvim-5.dtb.overlay.env`.
3. Reboot after changing the Overlay configuration.
4. Before recording, set the capture route and stop if it fails:

```bash
amixer -c 0 cset name='TDMIN_B source select' 'tdmin_b'
```

Do not start Whisper against `hw:0,1` until the Overlay is active after reboot
and the route command succeeds. The `ext-board-codec` Overlay shares pins with
I2S and SPI functions; avoid conflicting Overlays unless the mux configuration
has been confirmed.

Verify standalone recording before Whisper:

```bash
arecord -D hw:0,1 -f cd -c 2 -d 5 /tmp/analog-mic.wav
```

Use matching parameters for real-time recognition:

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_whisper.py \
  --enc assets/whisper/model/whisper_encoder_static_sim_w8a16.adla \
  --dec assets/whisper/model/whisper_decoder_static_sim_w8a16.adla \
  --tokenizer assets/whisper/tokenizer \
  --microphone \
  --device hw:0,1 \
  --capture-rate 44100 \
  --capture-channels 2 \
  --mic-channel 0 \
  --language auto
```

Use channel 1 or `mix` if channel 0 is silent or noisy.

## Endpointing and VAD tuning

At startup the script measures ambient RMS for 1.5 seconds. Keep quiet during
that interval. The automatic speech threshold is the larger of:

- ambient RMS multiplied by `--vad-ratio` (default 3.0)
- `--min-energy-threshold` (default 0.003)

Relevant options:

| Option | Default | Effect |
| --- | ---: | --- |
| `--chunk-ms` | 100 | Capture and VAD resolution. |
| `--pre-roll-ms` | 300 | Preserves audio immediately before speech detection. |
| `--min-speech-ms` | 300 | Rejects short impulses. |
| `--silence-ms` | 1000 | Quiet time before finalizing an utterance. |
| `--max-utterance-seconds` | 15 | Forces a result during continuous speech; maximum 30. |
| `--energy-threshold` | 0 | Zero uses calibration; a positive value fixes the RMS threshold. |

For lower latency, try `--silence-ms 700`. For missed speech, first check the
selected channel and calibration conditions, then lower the threshold. For
false triggers, raise it. Avoid calibrating while speaking.

## Output and language handling

Automatic detection includes the detected language and confidence:

```text
[001 | 2.6s | zh 96%] 你好，你现在好吗
[002 | 3.1s | en 94%] Hello, how are you?
```

Use `--language zh`, `--language en`, or another tokenizer-supported language
when all utterances use one known language. Very short or code-switched speech
can produce unstable automatic detection.

## Validation sequence

1. Run `scripts/vim-5_npu_status.py status` and resolve missing Whisper modules,
   assets, `arecord`, or ADLA device access.
2. Run file inference with a known WAV file and confirm text output.
3. Run `arecord -l` and a short recording with the exact device parameters.
4. For `hw:0,1`, verify `ext-board-codec` is active after reboot and run the
   required `amixer` route command before the short recording.
5. Start real-time inference, remain quiet during calibration, speak a sentence,
   then pause for at least `--silence-ms`.
6. If no text appears, inspect channel RMS or try another `--mic-channel` before
   changing VAD thresholds.

The runtime keeps the models loaded between utterances. Initial startup is
therefore slower than subsequent phrase recognition. Recording is buffered by a
reader thread during NPU inference so short following utterances are not lost.
