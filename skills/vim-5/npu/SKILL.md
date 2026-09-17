---
name: khadas-vim-5-npu
description: VIM 5 8 TOPS NPU application helper for Amlogic AMLNNLite workflows in the amlnnlite_py310 conda environment, including bundled YOLOv8n image/camera demos and bundled Whisper file or real-time microphone transcription. Use when setting up, running, adapting, or debugging VIM 5 ADLA inference, NPU dependencies, USB camera input, ALSA microphone input, speech recognition, or automatic spoken-language detection.
---

# VIM 5 NPU

## Scope

Use this skill for Khadas VIM 5 NPU application workflows on the integrated 8 TOPS NPU.

Naming rule:
- Use `vim-5` for executable script filenames and command examples.
- Use `vim_5` only where Python import syntax requires it.

Supported initial target:
- YOLOv8n ADLA still-image inference with `scripts/vim-5_yolov8n_image.py`
- YOLOv8n ADLA USB camera inference with `scripts/vim-5_yolov8n_usb_camera.py`
- YOLOv8n ADLA USB camera input with VIM 5 expansion-board SPI LCD summaries using `scripts/vim-5_yolov8n_usb_camera_spi_lcd.py`
- Whisper ADLA file transcription and endpointed real-time microphone transcription with `scripts/vim-5_whisper.py`
- Picoclaw local voice input with the bundled VIM 5 ARM64 JSONL runtime at `assets/whisper/bin/whisper_demo`
- Automatic Whisper language detection or an explicitly selected language such as `zh` or `en`
- VIM 5 PDM Mic Array capture from `hw:0,3` and analog MIC capture from `hw:0,1`
- Conda Python environment setup and runtime checks for `amlnnlite`, `cv2`, `numpy`, `transformers`, `librosa`, `.adla` model files, bundled scripts and assets, `/dev/video*`, and `arecord`
- ADLA device visibility checks for `/dev/adla*` and `/sys/class/adla/adla*`

The required YOLOv8n and Whisper `.adla` models, YOLOv8n sample image, and Whisper tokenizer are bundled under `assets/`. Do not hard-code or call any external reference-code path such as `~/whisper` in this skill. Treat external examples only as references for code logic.

## Default paths

Use these skill-relative paths unless the user provides alternatives:

```text
scripts/vim_5_yolov8n_core.py
scripts/vim_5_yolov8n_video.py
scripts/vim_5_yolov8n_spi_lcd.py
scripts/vim-5_yolov8n_image.py
scripts/vim-5_yolov8n_usb_camera.py
scripts/vim-5_yolov8n_usb_camera_spi_lcd.py
scripts/vim-5_whisper.py
scripts/vim-5_npu_status.py
assets/whisper/bin/whisper_demo
assets/whisper/data_bin/data.bin
assets/whisper/data_bin/tokenizer_info.bin
assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla
assets/yolov8n/input/test_image.png
assets/whisper/model/whisper_encoder_static_sim_w8a16.adla
assets/whisper/model/whisper_decoder_static_sim_w8a16.adla
assets/whisper/tokenizer/
```

The files below `assets/whisper/` form a self-contained runtime for Picoclaw's
`local_voice` channel. Use the installed skill directory as the process working
directory; do not point runtime configuration at a Whisper source checkout.

Generated inference commands use the bundled scripts and bundled assets by default. Override asset paths only when the user explicitly wants to run a different model, tokenizer, image set, or audio file.

## Python environment

Use the dedicated NPU conda environment by default:

```bash
conda create -n amlnnlite_py310 python=3.10 -y
conda activate amlnnlite_py310
for req in $(cat requirements.txt); do pip install $req; done
pip install opencv-python transformers librosa amlnn_edge_toolkit_lite-*-linux_aarch64.whl
```

Run these commands from the directory that contains `requirements.txt` and the `amlnn_edge_toolkit_lite-*-linux_aarch64.whl` file. If those files are not in the current directory, ask the user for the SDK/package directory or search the local filesystem.

For generated run commands, prefer non-interactive conda invocation:

```bash
conda run -n amlnnlite_py310 python ...
```

If `conda` is not on the non-interactive PATH, use the executable discovered by `scripts/vim-5_npu_status.py status`. The bundled helper auto-detects common miniforge, miniconda, and anaconda locations; pass `--conda /path/to/conda` to override it.

## Runtime dependency checks

Before running NPU inference:
1. Check that conda exists and that the `amlnnlite_py310` environment can run Python.
2. For YOLO, check `amlnnlite`, `cv2`, and `numpy`. For Whisper, check `amlnnlite`, `transformers`, `librosa`, and `numpy`.
3. Check the bundled `.adla` model and sample image exist before inference.
4. Check `ls -l /dev/adla*` and `/sys/class/adla/adla*`; VIM 5 normally exposes `/dev/adla0`.
5. Run the helper's AMLNNLite model-load probe before marking inference ready.
6. For USB camera inference, check `ls -l /dev/video*` and verify the selected camera can produce frames.
7. For USB camera + SPI LCD summaries, check `/dev/spidev1.0`, `spidev`, and either `gpiod` or `gpioset`. The combined program must run in a Python environment that can import both `amlnnlite` and `spidev`.
8. For real-time Whisper, check `arecord -l`; use the hardware rate and channel count for the selected ALSA device.
9. Before using analog MIC `hw:0,1`, require the expansion board to be connected and `fdt_overlays=ext-board-codec` to be active in `/boot/dtb/amlogic/kvim-5.dtb.overlay.env` after a reboot. Do not start analog capture when this precondition is unmet.
10. Before every `hw:0,1` capture session, configure the route with exactly `amixer -c 0 cset name='TDMIN_B source select' 'tdmin_b'`. Stop if this command fails.
11. If imports fail, diagnose the `amlnnlite_py310` conda environment and wheel installation before trying system Python or apt packages.

Use the bundled status helper:

```bash
scripts/vim-5_npu_status.py status
scripts/vim-5_npu_status.py setup-commands
scripts/vim-5_npu_status.py commands
```

`status` reports whether bundled image inference is ready and whether USB camera inference is ready. Image and USB camera inference use `amlnnlite`.
It also reports whether the bundled Whisper assets, Python modules, and `arecord` command are ready.
The USB camera + SPI LCD application reuses the VIM 5 hardware-control skill's `scripts/spi_lcd_st7735.py` helper for the low-level ST7735 display driver instead of duplicating board-control code. Keep `khadas-vim-5-hardware-control` installed or keep this repo's sibling `skills/vim-5/hardware-control` tree available.
If Codex is running in a restricted execution environment, it may not see `/dev/adla0` even when the user's shell can. In that case, trust a user-provided `ls /dev/adla*` result for device-node visibility, but still surface any AMLNNLite model-load probe failure separately.

## YOLOv8n image inference

Use:

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_yolov8n_image.py \
  --model-path assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla \
  --image-dir assets/yolov8n/input \
  --output-dir yolov8n_result
```

The script uses `amlnnlite.api.AMLNNLite` for runtime inference and writes result images under a model-named result directory.

## YOLOv8n USB camera inference

Use:

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_yolov8n_usb_camera.py \
  --model-path assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla \
  --camera /dev/video0 \
  --width 640 \
  --height 480 \
  --fps 30 \
  --display auto
```

For headless runs, add `--display off`. For a bounded test, add `--max-frames 30`. To save annotated video, add `--output /tmp/yolov8n_npu.mp4`.

## YOLOv8n USB camera + SPI LCD summaries

Use this when the input is a USB camera and the detection summary should be rendered on the VIM 5 expansion-board ST7735-compatible SPI LCD:

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_yolov8n_usb_camera_spi_lcd.py \
  --model-path assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla \
  --camera /dev/video0 \
  --width 640 \
  --height 480 \
  --fps 30 \
  --display off \
  --lcd on
```

For a bounded smoke test, add `--max-frames 30`. To disable the SPI LCD while testing NPU and camera logic, add `--lcd off`. To save annotated video, add `--output /tmp/yolov8n_npu_lcd.mp4`.

The SPI LCD path assumes the VIM 5 expansion-board display is exposed as `/dev/spidev1.0` after the `spi1-lcd` overlay is active and the board has rebooted. The default GPIO lines are `GPIOD_5` for reset and `GPIOM_1` for D/C, matching the bundled VIM 5 hardware-control SPI LCD helper.

## Whisper file transcription

Use a local audio file; `librosa` converts it to mono 16 kHz before inference:

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_whisper.py \
  --enc assets/whisper/model/whisper_encoder_static_sim_w8a16.adla \
  --dec assets/whisper/model/whisper_decoder_static_sim_w8a16.adla \
  --tokenizer assets/whisper/tokenizer \
  --audio-file /path/to/audio.wav \
  --language auto
```

`--language auto` detects the language for every segment and is the default. Use a fixed language such as `--language zh` when lower latency and stable single-language recognition matter more than detection.

## Whisper real-time microphone transcription

Whisper uses a fixed 30-second encoder input, but the bundled script pads short utterances and emits finalized text after a silence boundary. It keeps both NPU models loaded and continues capturing audio while inference runs. This is endpointed utterance streaming, not token-by-token streaming.

For Picoclaw `local_voice`, run the bundled JSONL producer from
`assets/whisper/`:

```bash
./bin/whisper_demo \
  --enc ./model/whisper_encoder_static_sim_w8a16.adla \
  --dec ./model/whisper_decoder_static_sim_w8a16.adla \
  --data-bin-dir ./data_bin \
  --microphone \
  --device hw:0,3 \
  --capture-rate 48000 \
  --capture-channels 6 \
  --mic-channel 0 \
  --language zh \
  --output-format jsonl
```

The installed asset root is normally
`~/.picoclaw/workspace/skills/khadas-vim-5-npu/assets/whisper`. The executable is
for VIM 5 ARM64 and dynamically uses the board's `libnnsdk.so`.

For the six-channel PDM Mic Array (`arecord -D hw:0,3 -r 48000 -f S16_LE -c 6`):

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

The two-channel analog MIC is not usable from `hw:0,1` until all of these conditions are met:

- The VIM 5 expansion board is connected.
- `/boot/dtb/amlogic/kvim-5.dtb.overlay.env` contains `fdt_overlays=ext-board-codec`, and the board has rebooted after that change.
- The capture route is configured before recording:

```bash
amixer -c 0 cset name='TDMIN_B source select' 'tdmin_b'
```

Only after the route command succeeds, use the analog MIC capture settings (`arecord -D hw:0,1 -f cd -c 2`, where `cd` means S16_LE/44100 Hz/stereo):

```bash
--device hw:0,1 --capture-rate 44100 --capture-channels 2 --mic-channel 0
```

Use `--mic-channel 1` to select the second channel or `--mic-channel mix` to average all captured channels. Keep quiet during the initial ambient-noise calibration. For faster finalization, reduce `--silence-ms` from 1000 to about 700; if speech is missed, lower `--energy-threshold` or `--min-energy-threshold` carefully.

## Troubleshooting

- If `ModuleNotFoundError: amlnnlite` appears, activate `amlnnlite_py310` and install `amlnn_edge_toolkit_lite-*-linux_aarch64.whl` into that environment.
- If `ModuleNotFoundError: cv2` appears, install `opencv-python` inside `amlnnlite_py310`.
- If `ModuleNotFoundError: transformers` or `librosa` appears, install both inside `amlnnlite_py310`.
- If `arecord` is missing, install `alsa-utils`. If capture fails, verify the selected device with `arecord -l` and do not substitute 16 kHz/mono values for hardware devices that require 48 kHz/6ch or 44.1 kHz/2ch.
- If analog MIC `hw:0,1` is unavailable or silent, first verify `ext-board-codec` is the active overlay after reboot, then rerun `amixer -c 0 cset name='TDMIN_B source select' 'tdmin_b'`. Do not treat VAD tuning as a substitute for these hardware-routing requirements.
- If Whisper never reports `Speech detected`, keep quiet during calibration, select another channel, or lower the RMS threshold. If noise triggers recognition repeatedly, raise the threshold.
- If Whisper produces unstable language results for very short or mixed-language speech, use a fixed `--language` value or speak a longer utterance.
- If `ModuleNotFoundError: spidev` appears in the USB camera + SPI LCD app, install `spidev` into the same Python environment that runs `amlnnlite`, for example `conda run -n amlnnlite_py310 pip install spidev`.
- If the SPI LCD GPIO dependency is missing, install `gpiod` and optionally `python3-libgpiod`; `gpioset` is enough for the bundled helper's fallback mode.
- If camera open fails, check the device path, permissions, USB connection, and whether another process owns the camera.
- If `/dev/spidev1.0` is missing, enable `spi1-lcd` and reboot before running the SPI LCD application.
- If `npu_runtime_probe` fails while `/dev/adla0` exists, check device permissions, whether the command is running inside a sandbox that cannot access device nodes, and whether another process owns the NPU runtime.
- If OpenCV preview fails, run with `--display off` or set a working `QT_QPA_PLATFORM` such as `wayland` or `xcb`.
- If model loading fails, verify the `.adla` file exists and matches the VIM 5 NPU runtime.

## Bundled references

- Consult `references/vim-5-npu-yolov8n.md` for YOLOv8n command patterns and example-specific notes.
- Consult `references/vim-5-npu-whisper.md` for Whisper assets, language handling, microphone profiles, VAD tuning, and validation steps.
