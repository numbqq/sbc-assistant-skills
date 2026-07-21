#!/usr/bin/env python3
"""Run YOLOv8n USB camera detection and show summaries on the VIM 5 SPI LCD."""

from __future__ import annotations

import argparse
from pathlib import Path
import signal
import sys
import time

import cv2
from amlnnlite.api import AMLNNLite as AMLNN

from vim_5_yolov8n_core import draw_detections, postprocess, preprocess_frame
from vim_5_yolov8n_spi_lcd import (
    DEFAULT_DC_LINE,
    DEFAULT_GPIO_MODE,
    DEFAULT_RESET_LINE,
    DEFAULT_SPEED_HZ,
    DEFAULT_SPI_DEVICE,
    LcdConfig,
    LcdNotifier,
    LcdState,
    lcd_state_summary,
    state_from_detections,
)
from vim_5_yolov8n_video import create_video_writer, draw_status, open_camera, select_display_backend


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = SKILL_ROOT / "assets" / "yolov8n" / "model" / "yolov8n_rawhead_w8a8_a311y3.adla"


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


def build_lcd_config(args: argparse.Namespace) -> LcdConfig:
    return LcdConfig(
        spi=args.spi,
        reset_line=args.reset_line,
        dc_line=args.dc_line,
        gpio_mode=args.gpio_mode,
        speed_hz=args.speed_hz,
        refresh_interval=args.lcd_refresh,
    )


def run(args: argparse.Namespace) -> int:
    if not args.model_path.exists():
        raise FileNotFoundError(f"model not found: {args.model_path}")

    stop = False

    def handle_signal(signum: int, frame: object) -> None:
        del signum, frame
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    backend = select_display_backend(args.display)
    show_window = backend is not None and args.display != "off"
    window_name = "VIM 5 YOLOv8n NPU LCD"
    cap = None
    writer = None
    lcd = None
    runtime_ready = False
    amlnn = AMLNN()

    try:
        if args.lcd == "on":
            lcd = LcdNotifier(build_lcd_config(args))
            lcd.open()
            lcd.show(LcdState((), 0), force=True)

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
        print(
            "spi_lcd="
            f"{args.lcd} mode=async max_items={args.lcd_max_items} refresh={args.lcd_refresh}s "
            f"device={args.spi}"
        )

        frame_count = 0
        fps_value = 0.0
        fps_clock = time.time()
        fps_frames = 0
        last_printed_key = None
        perf_enabled = args.perf_log_interval > 0
        perf_clock = time.time()
        perf_frames = 0
        perf_preprocess = 0.0
        perf_inference = 0.0
        perf_postprocess = 0.0
        perf_preview = 0.0

        while not stop:
            frame_count += 1
            loop_start = time.time()

            if perf_enabled:
                perf_step = time.perf_counter()
            input_tensor, resize_scale, pad = preprocess_frame(frame, input_shape, scale, zero_point, tensor_type)
            if perf_enabled:
                now_perf = time.perf_counter()
                perf_preprocess += now_perf - perf_step
                perf_step = now_perf

            outputs = amlnn.inference(inputs=[input_tensor])
            if perf_enabled:
                now_perf = time.perf_counter()
                perf_inference += now_perf - perf_step
                perf_step = now_perf

            detections = postprocess(outputs, input_shape, resize_scale, pad, args.conf, args.nms)
            if perf_enabled:
                now_perf = time.perf_counter()
                perf_postprocess += now_perf - perf_step
                perf_step = now_perf

            state = state_from_detections(detections, frame_w, args.lcd_max_items)
            if lcd is not None and lcd.show(state):
                if args.log and state.key != last_printed_key:
                    print(f"lcd_state={lcd_state_summary(state)} total={state.total_count}")
                    last_printed_key = state.key

            fps_frames += 1
            now = time.time()
            if now - fps_clock >= 1.0:
                fps_value = fps_frames / (now - fps_clock)
                fps_clock = now
                fps_frames = 0
            elif fps_value == 0.0:
                fps_value = 1.0 / max(now - loop_start, 1e-6)

            if show_window or writer is not None:
                result_frame = draw_detections(frame, detections)
                draw_status(result_frame, fps_value, len(detections))
                if writer is not None:
                    writer.write(result_frame)
                if show_window:
                    cv2.imshow(window_name, result_frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in (27, ord("q")):
                        break
                if perf_enabled:
                    now_perf = time.perf_counter()
                    perf_preview += now_perf - perf_step

            if perf_enabled:
                perf_frames += 1
                perf_elapsed = time.time() - perf_clock
                if perf_elapsed >= args.perf_log_interval:
                    frame_divisor = max(perf_frames, 1)
                    print(
                        f"perf loop_fps={perf_frames / perf_elapsed:.1f} "
                        f"preprocess_ms={perf_preprocess * 1000.0 / frame_divisor:.1f} "
                        f"npu_infer_ms={perf_inference * 1000.0 / frame_divisor:.1f} "
                        f"postprocess_ms={perf_postprocess * 1000.0 / frame_divisor:.1f} "
                        f"preview_ms={perf_preview * 1000.0 / frame_divisor:.1f} "
                        f"detections={len(detections)}"
                    )
                    perf_clock = time.time()
                    perf_frames = 0
                    perf_preprocess = 0.0
                    perf_inference = 0.0
                    perf_postprocess = 0.0
                    perf_preview = 0.0

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
        if lcd is not None:
            lcd.close()
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
    parser.add_argument("--display", choices=("auto", "on", "off"), default="off")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--output", default="")
    parser.add_argument("--perf-log-interval", type=float, default=0.0)
    parser.add_argument("--lcd", choices=("on", "off"), default="on")
    parser.add_argument("--lcd-max-items", type=int, choices=range(1, 6), default=5, metavar="1-5")
    parser.add_argument("--lcd-refresh", type=float, default=0.5)
    parser.add_argument("--spi", default=DEFAULT_SPI_DEVICE)
    parser.add_argument("--reset-line", default=DEFAULT_RESET_LINE)
    parser.add_argument("--dc-line", default=DEFAULT_DC_LINE)
    parser.add_argument("--gpio-mode", choices=("auto", "gpiod", "gpioset"), default=DEFAULT_GPIO_MODE)
    parser.add_argument("--speed-hz", type=int, default=DEFAULT_SPEED_HZ)
    parser.add_argument("--log", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except Exception as exc:
        print(f"vim-5_yolov8n_usb_camera_spi_lcd.py: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
