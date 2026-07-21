#!/usr/bin/env python3
"""Shared OpenCV camera, preview, and recording helpers for YOLOv8n apps."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np


WINDOW_PROBE_CODE = """
import cv2
import numpy as np

img = np.zeros((8, 8, 3), dtype=np.uint8)
cv2.namedWindow("vim-5_npu_probe", cv2.WINDOW_NORMAL)
cv2.imshow("vim-5_npu_probe", img)
cv2.waitKey(1)
cv2.destroyAllWindows()
"""


def parse_camera(camera: str | int) -> str | int:
    if isinstance(camera, int):
        return camera
    camera = str(camera)
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
