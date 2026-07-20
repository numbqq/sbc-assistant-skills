#!/usr/bin/env python3
"""Run YOLOv8n ADLA USB camera inference on the VIM 5 NPU."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from amlnnlite.api import AMLNNLite as AMLNN

from vim_5_yolov8n_core import draw_detections, postprocess, preprocess_frame


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = SKILL_ROOT / "assets" / "yolov8n" / "model" / "yolov8n_rawhead_w8a8_a311y3.adla"
WINDOW_PROBE_CODE = """
import cv2
import numpy as np
img = np.zeros((8, 8, 3), dtype=np.uint8)
cv2.namedWindow("vim-5_npu_probe", cv2.WINDOW_NORMAL)
cv2.imshow("vim-5_npu_probe", img)
cv2.waitKey(1)
cv2.destroyAllWindows()
"""


def parse_camera(camera: str):
    if camera.startswith("/dev/video"):
        return camera
    if camera.isdigit():
        return int(camera)
    return camera


def probe_qt_platform(platform: str) -> bool:
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = platform
    env.pop("QT_DEBUG_PLUGINS", None)
    try:
        proc = subprocess.run(
            [sys.executable, "-c", WINDOW_PROBE_CODE],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0


def select_display_backend(display: str) -> str | None:
    if display == "off":
        return None

    preferred = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
    candidates = ["wayland", "xcb"]
    if preferred in candidates:
        candidates = [preferred] + [item for item in candidates if item != preferred]

    for platform in candidates:
        if probe_qt_platform(platform):
            os.environ["QT_QPA_PLATFORM"] = platform
            return platform
    os.environ.pop("QT_QPA_PLATFORM", None)
    if display == "on":
        raise RuntimeError("OpenCV display requested but no working Qt platform was found")
    return None


def open_camera(camera: str, width: int, height: int, fps: float, fourcc: str):
    cap = cv2.VideoCapture(parse_camera(camera), cv2.CAP_V4L2)
    if not cap.isOpened():
        raise RuntimeError(f"failed to open camera: {camera}")

    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    if width > 0:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height > 0:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if fps > 0:
        cap.set(cv2.CAP_PROP_FPS, fps)

    ok, frame = cap.read()
    if not ok or frame is None:
        cap.release()
        raise RuntimeError(f"failed to read frame from camera: {camera}")
    return cap, frame


def create_video_writer(output_path: Path | None, fps: float, frame_size: tuple[int, int]):
    if output_path is None:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, frame_size)
    if not writer.isOpened():
        raise RuntimeError(f"failed to open video writer: {output_path}")
    return writer


def draw_status(frame: np.ndarray, fps: float, detection_count: int) -> None:
    label = f"FPS: {fps:.1f}  Objects: {detection_count}"
    cv2.rectangle(frame, (8, 8), (250, 38), (0, 0, 0), thickness=cv2.FILLED)
    cv2.putText(
        frame,
        label,
        (14, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        thickness=1,
        lineType=cv2.LINE_AA,
    )


def tensor_input_info(amlnn: AMLNN):
    tensor_attr = amlnn.get_tensor_info()["inputs"][0]
    input_h = int(tensor_attr["dims"][1])
    input_w = int(tensor_attr["dims"][2])
    return (
        (input_h, input_w),
        float(tensor_attr["scale"]),
        int(tensor_attr["zp"]),
        int(tensor_attr["type"]),
    )


def run(args: argparse.Namespace) -> int:
    if not args.model_path.exists():
        raise FileNotFoundError(f"model not found: {args.model_path}")

    backend = select_display_backend(args.display)
    show_window = backend is not None and args.display != "off"
    window_name = "VIM 5 YOLOv8n NPU"
    cap = None
    writer = None
    runtime_ready = False
    amlnn = AMLNN()

    try:
        amlnn.init_runtime(mode="native", enable_perf=True)
        runtime_ready = True
        amlnn.load_model(path=str(args.model_path))
        input_shape, scale, zero_point, tensor_type = tensor_input_info(amlnn)

        cap, frame = open_camera(args.camera, args.width, args.height, args.fps, args.fourcc)
        frame_h, frame_w = frame.shape[:2]
        output_path = Path(args.output) if args.output else None
        writer = create_video_writer(output_path, args.fps, (frame_w, frame_h))

        print(amlnn.get_sdk_version())
        print(f"model={args.model_path}")
        print(f"camera={args.camera} {frame_w}x{frame_h}")
        print(f"display={'on' if show_window else 'off'} backend={backend or 'none'}")

        frame_count = 0
        fps_value = 0.0
        fps_clock = time.time()
        fps_frames = 0
        while True:
            frame_count += 1
            loop_start = time.time()
            input_tensor, resize_scale, pad = preprocess_frame(frame, input_shape, scale, zero_point, tensor_type)
            outputs = amlnn.inference(inputs=[input_tensor])
            detections = postprocess(outputs, input_shape, resize_scale, pad, args.conf, args.nms)
            result_frame = draw_detections(frame, detections)

            fps_frames += 1
            now = time.time()
            if now - fps_clock >= 1.0:
                fps_value = fps_frames / (now - fps_clock)
                fps_clock = now
                fps_frames = 0
            elif fps_value == 0.0:
                fps_value = 1.0 / max(now - loop_start, 1e-6)
            draw_status(result_frame, fps_value, len(detections))

            if writer is not None:
                writer.write(result_frame)
            if show_window:
                cv2.imshow(window_name, result_frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
            if args.max_frames > 0 and frame_count >= args.max_frames:
                break

            ok, frame = cap.read()
            if not ok or frame is None:
                raise RuntimeError(f"failed to read frame from camera: {args.camera}")

        print(f"frames={frame_count}")
        print(amlnn.get_perf_info())
        return 0
    except KeyboardInterrupt:
        print("interrupted")
        return 130
    finally:
        if writer is not None:
            writer.release()
        if cap is not None:
            cap.release()
        if show_window:
            cv2.destroyAllWindows()
        if runtime_ready:
            amlnn.uninit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--camera", default="/dev/video0")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--fourcc", default="MJPG")
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--nms", type=float, default=0.4)
    parser.add_argument("--display", choices=("auto", "on", "off"), default="auto")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--output", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
