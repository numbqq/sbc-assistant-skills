# VIM 5 NPU YOLOv8n Reference

## Target

- Board: Khadas VIM 5
- NPU: integrated 8 TOPS NPU
- Runtime model format: `.adla`
- Runtime Python API: `amlnnlite.api.AMLNNLite`
- Python environment: conda env `amlnnlite_py310` with Python 3.10

## Bundled scripts

Executable entries use `vim-5`; the shared import module uses `vim_5`.

```text
scripts/vim_5_yolov8n_core.py
scripts/vim_5_yolov8n_video.py
scripts/vim_5_yolov8n_spi_lcd.py
scripts/vim-5_yolov8n_image.py
scripts/vim-5_yolov8n_usb_camera.py
scripts/vim-5_yolov8n_usb_camera_spi_lcd.py
scripts/vim-5_npu_status.py
```

The image, USB camera, and USB camera + SPI LCD scripts contain the adapted YOLOv8n preprocessing, AMLNNLite inference, postprocessing, NMS, and drawing logic. They do not import or execute external reference scripts. The SPI LCD application reuses the VIM 5 hardware-control skill's ST7735 helper for low-level display I/O.

## Bundled assets

```text
assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla
assets/yolov8n/input/test_image.png
```

The ONNX model is not bundled because runtime inference only needs `.adla`.

## Python setup

Run from the directory that contains `requirements.txt` and the NPU runtime wheel:

```bash
conda create -n amlnnlite_py310 python=3.10 -y
conda activate amlnnlite_py310
for req in $(cat requirements.txt); do pip install $req; done
pip install opencv-python amlnn_edge_toolkit_lite-*-linux_aarch64.whl
```

If the package files are not in the current directory, locate the SDK/package directory before running install commands, or pass it to `scripts/vim-5_npu_status.py setup-commands --setup-dir`.

## Useful status checks

```bash
scripts/vim-5_npu_status.py status
scripts/vim-5_npu_status.py setup-commands --setup-dir /path/to/sdk
scripts/vim-5_npu_status.py commands
conda run -n amlnnlite_py310 python -c 'import sys; print(sys.executable)'
conda run -n amlnnlite_py310 python -c 'import amlnnlite, cv2, numpy'
ls -l /dev/adla*
ls -d /sys/class/adla/adla*
ls -l /dev/video*
ls -l /dev/spidev1.0
```

If non-interactive commands cannot find `conda`, use the executable detected by `scripts/vim-5_npu_status.py status` or pass `--conda /path/to/conda`.
VIM 5 normally exposes `/dev/adla0`. If the user's shell sees `/dev/adla0` but a tool-run status command does not, treat that as execution-environment isolation and run the final inference command from the user's shell or another environment with device access.

## Image inference

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_yolov8n_image.py \
  --model-path assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla \
  --image-dir assets/yolov8n/input \
  --output-dir yolov8n_result
```

The script loads the ADLA model with AMLNNLite, letterboxes images, converts BGR to RGB, quantizes according to the model input tensor metadata, runs NPU inference, postprocesses raw YOLOv8 head outputs, applies class-aware NMS, and writes annotated result images.

## USB camera inference

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_yolov8n_usb_camera.py \
  --model-path assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla \
  --camera /dev/video0 \
  --width 640 \
  --height 480 \
  --fps 30 \
  --fourcc MJPG \
  --display auto
```

Headless or SSH run:

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_yolov8n_usb_camera.py \
  --model-path assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla \
  --camera /dev/video0 \
  --display off \
  --max-frames 30
```

Optional video output:

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_yolov8n_usb_camera.py \
  --model-path assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla \
  --camera /dev/video0 \
  --display off \
  --output /tmp/yolov8n_npu.mp4
```

## USB camera + SPI LCD summaries

The input is a USB camera; the output summary is drawn to the VIM 5 expansion-board SPI LCD through `/dev/spidev1.0`.

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_yolov8n_usb_camera_spi_lcd.py \
  --model-path assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla \
  --camera /dev/video0 \
  --width 640 \
  --height 480 \
  --fps 30 \
  --fourcc MJPG \
  --display off \
  --lcd on
```

Headless bounded test:

```bash
conda run -n amlnnlite_py310 python scripts/vim-5_yolov8n_usb_camera_spi_lcd.py \
  --model-path assets/yolov8n/model/yolov8n_rawhead_w8a8_a311y3.adla \
  --camera /dev/video0 \
  --display off \
  --max-frames 30
```

The app imports `vim_5_yolov8n_core.py` for YOLO preprocessing/postprocessing, `vim_5_yolov8n_video.py` for OpenCV camera/preview/recording helpers, and `vim_5_yolov8n_spi_lcd.py` for detection-to-LCD rendering. The renderer loads `spi_lcd_st7735.py` from the sibling `skills/vim-5/hardware-control` tree or from the installed `khadas-vim-5-hardware-control` skill.

## Troubleshooting

- `ModuleNotFoundError: amlnnlite`: activate `amlnnlite_py310` and install `amlnn_edge_toolkit_lite-*-linux_aarch64.whl`.
- `ModuleNotFoundError: cv2`: install `opencv-python` in `amlnnlite_py310`.
- `ModuleNotFoundError: spidev`: install `spidev` into the same Python environment as `amlnnlite`, for example `conda run -n amlnnlite_py310 pip install spidev`.
- Missing `/dev/spidev1.0`: enable the `spi1-lcd` overlay and reboot.
- `npu_runtime_probe=missing` while `/dev/adla0` exists: check device permissions, sandbox/device access, and whether another process owns the ADLA runtime.
- `failed to open camera`: check `/dev/video*`, USB connection, camera permissions, and whether another process is using the camera.
- OpenCV preview failure: use `--display off`, or set a working `QT_QPA_PLATFORM` such as `wayland` or `xcb`.
- Model load failure: verify the `.adla` file exists and matches the VIM 5 NPU runtime.
