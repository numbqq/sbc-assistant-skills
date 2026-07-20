#!/usr/bin/env python3
"""Run YOLOv8n ADLA image inference on the VIM 5 NPU."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
from amlnnlite.api import AMLNNLite as AMLNN

from vim_5_yolov8n_core import draw_detections, postprocess, preprocess_image

SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = SKILL_ROOT / "assets" / "yolov8n" / "model" / "yolov8n_rawhead_w8a8_a311y3.adla"
DEFAULT_IMAGE_DIR = SKILL_ROOT / "assets" / "yolov8n" / "input"


def image_files(image_dir: Path) -> list[Path]:
    patterns = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.JPG", "*.JPEG", "*.PNG", "*.BMP")
    files: list[Path] = []
    for pattern in patterns:
        files.extend(image_dir.glob(pattern))
    return sorted(path for path in files if path.is_file())


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
    model_path = args.model_path
    image_dir = args.image_dir
    output_dir = args.output_dir

    if not model_path.exists():
        raise FileNotFoundError(f"model not found: {model_path}")
    if not image_dir.exists():
        raise FileNotFoundError(f"image directory not found: {image_dir}")

    files = image_files(image_dir)
    if not files:
        raise FileNotFoundError(f"no image files found in: {image_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    amlnn = AMLNN()
    runtime_ready = False
    try:
        amlnn.init_runtime(mode="native", enable_perf=True)
        runtime_ready = True
        amlnn.load_model(path=str(model_path))
        input_shape, scale, zero_point, tensor_type = tensor_input_info(amlnn)

        print(amlnn.get_sdk_version())
        print(f"model={model_path}")
        print(f"image_dir={image_dir}")
        print(f"output_dir={output_dir}")
        print(f"image_count={len(files)}")

        for idx, image_path in enumerate(files, 1):
            input_tensor, original_img, resize_scale, pad = preprocess_image(
                image_path,
                input_shape,
                scale,
                zero_point,
                tensor_type,
            )
            outputs = amlnn.inference(inputs=[input_tensor])
            detections = postprocess(outputs, input_shape, resize_scale, pad, args.conf, args.nms)
            result_img = draw_detections(original_img, detections)
            save_path = output_dir / f"{image_path.stem}_result.jpg"
            cv2.imwrite(str(save_path), result_img)

            print(f"image={idx}/{len(files)}:{image_path.name}")
            print(f"detections={len(detections)}")
            for det_idx, det in enumerate(detections, 1):
                print(f"  {det_idx}. {det['class_name']} {det['confidence']:.3f}")
            print(f"saved={save_path}")

        print(amlnn.get_perf_info())
        if args.perf_visualize:
            amlnn.perf_visualize()
        return 0
    finally:
        if runtime_ready:
            amlnn.uninit()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--image-dir", type=Path, default=DEFAULT_IMAGE_DIR)
    parser.add_argument("--output-dir", type=Path, default=Path("yolov8n_result"))
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--nms", type=float, default=0.4)
    parser.add_argument("--perf-visualize", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    return run(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
