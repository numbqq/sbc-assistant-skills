#!/usr/bin/env python3
"""Shared YOLOv8n preprocessing, postprocessing, and drawing helpers."""

from __future__ import annotations

import colorsys
from pathlib import Path

import cv2
import numpy as np


CLASS_NAMES = {
    0: "person",
    1: "bicycle",
    2: "car",
    3: "motorcycle",
    4: "airplane",
    5: "bus",
    6: "train",
    7: "truck",
    8: "boat",
    9: "traffic light",
    10: "fire hydrant",
    11: "stop sign",
    12: "parking meter",
    13: "bench",
    14: "bird",
    15: "cat",
    16: "dog",
    17: "horse",
    18: "sheep",
    19: "cow",
    20: "elephant",
    21: "bear",
    22: "zebra",
    23: "giraffe",
    24: "backpack",
    25: "umbrella",
    26: "handbag",
    27: "tie",
    28: "suitcase",
    29: "frisbee",
    30: "skis",
    31: "snowboard",
    32: "sports ball",
    33: "kite",
    34: "baseball bat",
    35: "baseball glove",
    36: "skateboard",
    37: "surfboard",
    38: "tennis racket",
    39: "bottle",
    40: "wine glass",
    41: "cup",
    42: "fork",
    43: "knife",
    44: "spoon",
    45: "bowl",
    46: "banana",
    47: "apple",
    48: "sandwich",
    49: "orange",
    50: "broccoli",
    51: "carrot",
    52: "hot dog",
    53: "pizza",
    54: "doughnut",
    55: "cake",
    56: "chair",
    57: "couch",
    58: "potted plant",
    59: "bed",
    60: "dining table",
    61: "toilet",
    62: "tv",
    63: "laptop",
    64: "mouse",
    65: "remote",
    66: "keyboard",
    67: "cell phone",
    68: "microwave",
    69: "oven",
    70: "toaster",
    71: "sink",
    72: "refrigerator",
    73: "book",
    74: "clock",
    75: "vase",
    76: "scissors",
    77: "teddy bear",
    78: "hair drier",
    79: "toothbrush",
}


def letterbox(img: np.ndarray, new_shape: tuple[int, int], color: tuple[int, int, int] = (114, 114, 114)):
    src_h, src_w = img.shape[:2]
    dst_h, dst_w = new_shape
    scale = min(dst_h / src_h, dst_w / src_w)
    resized_w = int(round(src_w * scale))
    resized_h = int(round(src_h * scale))

    if (src_w, src_h) != (resized_w, resized_h):
        img = cv2.resize(img, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)

    pad_h = dst_h - resized_h
    pad_w = dst_w - resized_w
    top = pad_h // 2
    bottom = pad_h - top
    left = pad_w // 2
    right = pad_w - left
    img = cv2.copyMakeBorder(img, top, bottom, left, right, cv2.BORDER_CONSTANT, value=color)
    return img, scale, (left, top)


def quantize_rgb_image(rgb_img: np.ndarray, tensor_scale: float, zero_point: int, tensor_type: int) -> np.ndarray:
    if tensor_type in (2, 3):
        inv_scale = np.float32(1.0 / (255.0 * tensor_scale))
        raw_val = np.round((rgb_img * inv_scale) + zero_point)
        if tensor_type == 2:
            return np.clip(raw_val, -128, 127).astype(np.int8)
        return np.clip(raw_val, 0, 255).astype(np.uint8)
    return (rgb_img * np.float32(1.0 / 255.0)).astype(np.float32)


def preprocess_frame(
    frame: np.ndarray,
    input_shape: tuple[int, int],
    tensor_scale: float,
    zero_point: int,
    tensor_type: int,
):
    processed_img, resize_scale, pad = letterbox(frame, input_shape)
    rgb_img = cv2.cvtColor(processed_img, cv2.COLOR_BGR2RGB)
    input_tensor = quantize_rgb_image(rgb_img, tensor_scale, zero_point, tensor_type)
    return np.expand_dims(input_tensor, axis=0), resize_scale, pad


def preprocess_image(
    image_path: Path,
    input_shape: tuple[int, int],
    tensor_scale: float,
    zero_point: int,
    tensor_type: int,
):
    original_img = cv2.imread(str(image_path))
    if original_img is None:
        raise ValueError(f"failed to read image: {image_path}")
    input_tensor, resize_scale, pad = preprocess_frame(
        original_img,
        input_shape,
        tensor_scale,
        zero_point,
        tensor_type,
    )
    return input_tensor, original_img, resize_scale, pad


def postprocess(
    outputs,
    input_shape: tuple[int, int],
    scale: float,
    pad: tuple[int, int],
    conf_threshold: float,
    iou_threshold: float,
    data_format: str = "NHWC",
    regmax: int = 16,
):
    input_h, input_w = input_shape
    all_boxes = []
    all_scores = []
    all_class_ids = []
    safe_thresh = np.clip(conf_threshold, 1e-5, 1.0 - 1e-5)
    inv_thresh = np.log(safe_thresh / (1.0 - safe_thresh))
    regression_range = np.arange(regmax, dtype=np.float32)
    reg_channels = 4 * regmax

    for idx, output in enumerate(outputs):
        if data_format == "NCHW":
            _, channels, height, width = output.shape
            output_reshaped = output.transpose(0, 2, 3, 1).reshape(-1, channels)
        elif data_format == "NHWC":
            _, height, width, channels = output.shape
            output_reshaped = output.reshape(-1, channels)
        else:
            raise ValueError(f"unsupported data format: {data_format}")

        stride = [32, 16, 8][idx]
        dfl_preds = output_reshaped[:, :reg_channels]
        class_preds = output_reshaped[:, reg_channels:]
        max_raw_scores = np.max(class_preds, axis=1)
        valid_mask = max_raw_scores > inv_thresh
        valid_indices = np.where(valid_mask)[0]
        if len(valid_indices) == 0:
            continue

        valid_class_preds = class_preds[valid_indices]
        valid_dfl_preds = dfl_preds[valid_indices]
        valid_class_scores = 1.0 / (1.0 + np.exp(-valid_class_preds))
        max_class_scores = np.max(valid_class_scores, axis=1)
        class_ids = np.argmax(valid_class_scores, axis=1)

        grid_y = (valid_indices // width).astype(np.float32)
        grid_x = (valid_indices % width).astype(np.float32)
        dfl_reshaped = valid_dfl_preds.reshape(-1, 4, regmax)
        dfl_max = np.max(dfl_reshaped, axis=-1, keepdims=True)
        exp_dfl = np.exp(dfl_reshaped - dfl_max)
        dfl_softmax = exp_dfl / np.sum(exp_dfl, axis=-1, keepdims=True)
        bbox_deltas = np.sum(dfl_softmax * regression_range[None, None, :], axis=-1)

        anchor_x = (grid_x + 0.5) * stride
        anchor_y = (grid_y + 0.5) * stride
        left, top, right, bottom = bbox_deltas.T
        boxes = np.stack(
            [
                anchor_x - left * stride,
                anchor_y - top * stride,
                anchor_x + right * stride,
                anchor_y + bottom * stride,
            ],
            axis=1,
        )
        all_boxes.append(boxes)
        all_scores.append(max_class_scores)
        all_class_ids.append(class_ids)

    if not all_boxes:
        return []

    valid_boxes = np.concatenate(all_boxes, axis=0)
    valid_scores = np.concatenate(all_scores, axis=0)
    valid_class_ids = np.concatenate(all_class_ids, axis=0)
    pad_x, pad_y = pad
    valid_boxes[:, [0, 2]] = (valid_boxes[:, [0, 2]] - pad_x) / scale
    valid_boxes[:, [1, 3]] = (valid_boxes[:, [1, 3]] - pad_y) / scale
    valid_boxes = np.maximum(valid_boxes, 0)

    max_coord = float(max(np.max(valid_boxes[:, 2]), np.max(valid_boxes[:, 3]), input_h, input_w)) + 1.0
    offsets = valid_class_ids.astype(valid_boxes.dtype) * max_coord
    widths = valid_boxes[:, 2] - valid_boxes[:, 0]
    heights = valid_boxes[:, 3] - valid_boxes[:, 1]
    boxes_xywh = np.stack([valid_boxes[:, 0] + offsets, valid_boxes[:, 1] + offsets, widths, heights], axis=1)
    nms_indices = cv2.dnn.NMSBoxes(
        boxes_xywh.tolist(),
        valid_scores.tolist(),
        conf_threshold,
        iou_threshold,
    )

    detections = []
    if len(nms_indices) > 0:
        for nms_idx in nms_indices.flatten():
            x1, y1, x2, y2 = valid_boxes[nms_idx]
            class_id = int(valid_class_ids[nms_idx])
            detections.append(
                {
                    "bbox": [float(x1), float(y1), float(x2), float(y2)],
                    "confidence": float(valid_scores[nms_idx]),
                    "class_id": class_id,
                    "class_name": CLASS_NAMES.get(class_id, f"class_{class_id}"),
                }
            )
    return detections


def class_color(class_id: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    hue = (class_id * 137.508) % 360
    rgb = colorsys.hsv_to_rgb(hue / 360.0, 0.8, 0.9)
    bgr = (int(rgb[2] * 255), int(rgb[1] * 255), int(rgb[0] * 255))
    text_color = (255, 255, 255) if sum(bgr) < 400 else (0, 0, 0)
    return bgr, text_color


def draw_detections(img: np.ndarray, detections, in_place: bool = False) -> np.ndarray:
    result_img = img if in_place else img.copy()
    for det in detections:
        x1, y1, x2, y2 = [int(value) for value in det["bbox"]]
        class_id = int(det["class_id"])
        confidence = float(det["confidence"])
        label = f"{det['class_name']}: {confidence:.2f}"
        color, text_color = class_color(class_id)
        cv2.rectangle(result_img, (x1, y1), (x2, y2), color, 2)

        (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        y1_label = max(y1, label_h + 10)
        cv2.rectangle(
            result_img,
            (x1, y1_label - label_h - 10),
            (x1 + label_w, y1_label),
            color,
            thickness=cv2.FILLED,
        )
        cv2.putText(
            result_img,
            label,
            (x1, y1_label - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            text_color,
            thickness=1,
            lineType=cv2.LINE_AA,
        )
    return result_img
