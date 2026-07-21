---
name: khadas-vim-5-npu
description: VIM 5 8 TOPS NPU application helper for running, generating, and debugging Python workflows with the amlnnlite_py310 conda environment, Amlogic AMLNNLite, bundled YOLOv8n ADLA model and sample image assets, bundled YOLOv8n image inference, bundled YOLOv8n USB camera inference, OpenCV camera/display handling, and runtime dependency checks. Use when Codex needs to set up or check the VIM 5 NPU runtime environment, run the bundled .adla model, troubleshoot amlnnlite/cv2/numpy imports, inspect USB camera devices, or adapt the bundled YOLOv8n NPU scripts.
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
- Conda Python environment setup and runtime checks for `amlnnlite`, `cv2`, `numpy`, `.adla` model files, bundled scripts, bundled images, and `/dev/video*`
- ADLA device visibility checks for `/dev/adla*` and `/sys/class/adla/adla*`

The required YOLOv8n `.adla` inference model and a sample image are bundled under `assets/`. Do not hard-code or call any external reference-code path in this skill. Treat external examples only as references for code logic.

## Default paths

Use these skill-relative paths unless the user provides alternatives:

```text
scripts/vim_5_yolov8n_core.py
scripts/vim_5_yolov8n_video.py
scripts/vim_5_yolov8n_spi_lcd.py
scripts/vim-5_yolov8n_image.py
scripts/vim-5_yolov8n_usb_camera.py
scripts/vim-5_yolov8n_usb_camera_spi_lcd.py
scripts/vim-5_npu_status.py
assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla
assets/yolov8n/input/test_image.png
```

Generated inference commands use the bundled scripts and bundled assets by default. Override `--model-path` or `--image-dir` only when the user explicitly wants to run a different `.adla` model or image set.

## Python environment

Use the dedicated NPU conda environment by default:

```bash
conda create -n amlnnlite_py310 python=3.10 -y
conda activate amlnnlite_py310
for req in $(cat requirements.txt); do pip install $req; done
pip install opencv-python amlnn_edge_toolkit_lite-*-linux_aarch64.whl
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
2. Check runtime modules with `conda run -n amlnnlite_py310 python -c 'import amlnnlite, cv2, numpy'` for inference.
3. Check the bundled `.adla` model and sample image exist before inference.
4. Check `ls -l /dev/adla*` and `/sys/class/adla/adla*`; VIM 5 normally exposes `/dev/adla0`.
5. Run the helper's AMLNNLite model-load probe before marking inference ready.
6. For USB camera inference, check `ls -l /dev/video*` and verify the selected camera can produce frames.
7. For USB camera + SPI LCD summaries, check `/dev/spidev1.0`, `spidev`, and either `gpiod` or `gpioset`. The combined program must run in a Python environment that can import both `amlnnlite` and `spidev`.
8. If imports fail, diagnose the `amlnnlite_py310` conda environment and wheel installation before trying system Python or apt packages.

Use the bundled status helper:

```bash
scripts/vim-5_npu_status.py status
scripts/vim-5_npu_status.py setup-commands
scripts/vim-5_npu_status.py commands
```

`status` reports whether bundled image inference is ready and whether USB camera inference is ready. Image and USB camera inference use `amlnnlite`.
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

## Troubleshooting

- If `ModuleNotFoundError: amlnnlite` appears, activate `amlnnlite_py310` and install `amlnn_edge_toolkit_lite-*-linux_aarch64.whl` into that environment.
- If `ModuleNotFoundError: cv2` appears, install `opencv-python` inside `amlnnlite_py310`.
- If `ModuleNotFoundError: spidev` appears in the USB camera + SPI LCD app, install `spidev` into the same Python environment that runs `amlnnlite`, for example `conda run -n amlnnlite_py310 pip install spidev`.
- If the SPI LCD GPIO dependency is missing, install `gpiod` and optionally `python3-libgpiod`; `gpioset` is enough for the bundled helper's fallback mode.
- If camera open fails, check the device path, permissions, USB connection, and whether another process owns the camera.
- If `/dev/spidev1.0` is missing, enable `spi1-lcd` and reboot before running the SPI LCD application.
- If `npu_runtime_probe` fails while `/dev/adla0` exists, check device permissions, whether the command is running inside a sandbox that cannot access device nodes, and whether another process owns the NPU runtime.
- If OpenCV preview fails, run with `--display off` or set a working `QT_QPA_PLATFORM` such as `wayland` or `xcb`.
- If model loading fails, verify the `.adla` file exists and matches the VIM 5 NPU runtime.

## Bundled references

Consult `references/vim-5-npu-yolov8n.md` for exact command patterns and example-specific notes.
