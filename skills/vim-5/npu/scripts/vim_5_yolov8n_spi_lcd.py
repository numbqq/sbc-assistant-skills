#!/usr/bin/env python3
"""SPI LCD state and rendering helpers for YOLOv8n detection summaries."""

from __future__ import annotations

import importlib.util
import queue
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType


WIDTH = 160
HEIGHT = 80

DEFAULT_SPI_DEVICE = "/dev/spidev1.0"
DEFAULT_RESET_LINE = "GPIOD_5"
DEFAULT_DC_LINE = "GPIOM_1"
DEFAULT_GPIO_MODE = "auto"
DEFAULT_SPEED_HZ = 8_000_000

BLACK = 0x0000
WHITE = 0xFFFF
RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F
YELLOW = 0xFFE0
CYAN = 0x07FF


def rgb565(red: int, green: int, blue: int) -> int:
    return ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)


ORANGE = rgb565(255, 128, 24)
DARK = rgb565(4, 10, 14)
GRAY = rgb565(96, 112, 120)
SOFT_GREEN = rgb565(90, 220, 150)
MAGENTA = rgb565(230, 90, 210)

VEHICLE_CLASSES = {"bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat"}
ANIMAL_CLASSES = {"bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"}
FOOD_CLASSES = {
    "banana",
    "apple",
    "sandwich",
    "orange",
    "broccoli",
    "carrot",
    "hot dog",
    "pizza",
    "doughnut",
    "cake",
}
DRINK_CLASSES = {"bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl"}
SCREEN_CLASSES = {"tv", "laptop", "mouse", "remote", "keyboard", "cell phone"}
FURNITURE_CLASSES = {"bench", "chair", "couch", "potted plant", "bed", "dining table", "toilet"}

LABEL_CODES = {
    "person": "PER",
    "bicycle": "BIKE",
    "car": "CAR",
    "motorcycle": "MOTO",
    "airplane": "AIR",
    "bus": "BUS",
    "train": "TRN",
    "truck": "TRK",
    "boat": "BOAT",
    "traffic light": "LITE",
    "fire hydrant": "HYD",
    "stop sign": "STOP",
    "parking meter": "MTR",
    "bench": "BNCH",
    "bird": "BIRD",
    "cat": "CAT",
    "dog": "DOG",
    "horse": "HORS",
    "sheep": "SHP",
    "cow": "COW",
    "elephant": "ELE",
    "bear": "BEAR",
    "zebra": "ZEB",
    "giraffe": "GIR",
    "backpack": "BAG",
    "umbrella": "UMB",
    "handbag": "BAG",
    "suitcase": "CASE",
    "sports ball": "BALL",
    "bottle": "BOTL",
    "wine glass": "GLAS",
    "cup": "CUP",
    "fork": "FORK",
    "knife": "KNIF",
    "spoon": "SPON",
    "bowl": "BOWL",
    "banana": "BANA",
    "apple": "APPL",
    "sandwich": "SAND",
    "orange": "ORNG",
    "pizza": "PIZA",
    "chair": "CHAR",
    "couch": "SOFA",
    "potted plant": "PLNT",
    "bed": "BED",
    "dining table": "TBL",
    "tv": "TV",
    "laptop": "LAPT",
    "mouse": "MOUS",
    "remote": "REMT",
    "keyboard": "KEYB",
    "cell phone": "PHON",
    "book": "BOOK",
    "clock": "CLK",
    "vase": "VASE",
    "scissors": "SCIS",
    "teddy bear": "TOY",
    "toothbrush": "BRSH",
}

_LCD_HELPER: ModuleType | None = None
_LCD_HELPER_PATH: Path | None = None


@dataclass(frozen=True)
class LcdConfig:
    spi: str = DEFAULT_SPI_DEVICE
    reset_line: str = DEFAULT_RESET_LINE
    dc_line: str = DEFAULT_DC_LINE
    gpio_mode: str = DEFAULT_GPIO_MODE
    speed_hz: int = DEFAULT_SPEED_HZ
    refresh_interval: float = 0.5


@dataclass(frozen=True)
class LcdItem:
    icon: str
    label: str
    confidence: float
    x_center: float

    @property
    def key(self) -> tuple[str, str, int, int]:
        confidence_bucket = min(9, max(0, int(self.confidence * 10.0)))
        position_bucket = min(9, max(0, int(self.x_center * 10.0)))
        return (self.icon, self.label, confidence_bucket, position_bucket)


@dataclass(frozen=True)
class LcdState:
    items: tuple[LcdItem, ...]
    total_count: int

    @property
    def key(self) -> tuple[object, ...]:
        return (self.total_count, tuple(item.key for item in self.items))


def lcd_helper_candidates() -> tuple[Path, ...]:
    skill_root = Path(__file__).resolve().parents[1]
    board_root = skill_root.parent
    return (
        board_root / "hardware-control" / "scripts" / "spi_lcd_st7735.py",
        Path.home() / ".codex" / "skills" / "khadas-vim-5-hardware-control" / "scripts" / "spi_lcd_st7735.py",
    )


def load_lcd_helper(helper_path: Path | None = None) -> ModuleType:
    global _LCD_HELPER, _LCD_HELPER_PATH
    if helper_path is None and _LCD_HELPER is not None:
        return _LCD_HELPER

    candidates = (helper_path,) if helper_path is not None else lcd_helper_candidates()
    for candidate in candidates:
        if candidate is None or not candidate.exists():
            continue
        spec = importlib.util.spec_from_file_location("vim5_spi_lcd_st7735", candidate)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        if helper_path is None:
            _LCD_HELPER = module
            _LCD_HELPER_PATH = candidate
        return module
    searched = ", ".join(str(path) for path in candidates if path is not None)
    raise RuntimeError(f"spi_lcd_st7735.py not found; searched: {searched}")


def loaded_lcd_helper_path() -> Path | None:
    return _LCD_HELPER_PATH


def set_pixel(pixels: list[int], x: int, y: int, color: int) -> None:
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        pixels[y * WIDTH + x] = color


def draw_line(pixels: list[int], x0: int, y0: int, x1: int, y1: int, color: int, thickness: int = 1) -> None:
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    radius = max(0, thickness // 2)

    while True:
        for yy in range(y0 - radius, y0 + radius + 1):
            for xx in range(x0 - radius, x0 + radius + 1):
                set_pixel(pixels, xx, yy, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def draw_circle(pixels: list[int], cx: int, cy: int, radius: int, color: int, thickness: int = 1) -> None:
    inner = max(0, radius - thickness + 1)
    outer2 = radius * radius
    inner2 = inner * inner
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            dist2 = (x - cx) * (x - cx) + (y - cy) * (y - cy)
            if inner2 <= dist2 <= outer2:
                set_pixel(pixels, x, y, color)


def fill_circle(pixels: list[int], cx: int, cy: int, radius: int, color: int) -> None:
    radius2 = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= radius2:
                set_pixel(pixels, x, y, color)


def draw_box(helper: ModuleType, pixels: list[int], x: int, y: int, w: int, h: int, color: int, thickness: int = 1) -> None:
    helper.draw_rect(pixels, x, y, w, thickness, color)
    helper.draw_rect(pixels, x, y + h - thickness, w, thickness, color)
    helper.draw_rect(pixels, x, y, thickness, h, color)
    helper.draw_rect(pixels, x + w - thickness, y, thickness, h, color)


def icon_for_class(class_name: str) -> str:
    if class_name == "person":
        return "person"
    if class_name in VEHICLE_CLASSES:
        return "vehicle"
    if class_name in ANIMAL_CLASSES:
        return "animal"
    if class_name in FOOD_CLASSES:
        return "food"
    if class_name in DRINK_CLASSES:
        return "drink"
    if class_name in SCREEN_CLASSES:
        return "screen"
    if class_name in FURNITURE_CLASSES:
        return "furniture"
    return "object"


def sanitize_label(label: str, max_len: int = 18) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ./-_:")
    clean = "".join(ch if ch in allowed else " " for ch in label)
    clean = " ".join(clean.split())
    return clean[:max_len] or "object"


def label_code(label: str) -> str:
    if label in LABEL_CODES:
        return LABEL_CODES[label]
    clean = sanitize_label(label, 12).replace(" ", "")
    return (clean[:4] or "OBJ").upper()


def icon_color(icon: str) -> int:
    return {
        "person": CYAN,
        "vehicle": ORANGE,
        "animal": SOFT_GREEN,
        "food": YELLOW,
        "drink": CYAN,
        "screen": BLUE,
        "furniture": MAGENTA,
        "object": WHITE,
    }.get(icon, WHITE)


def detection_x_center(detection: dict, frame_width: int) -> float:
    bbox = detection.get("bbox") or [0.0, 0.0, 0.0, 0.0]
    try:
        x_center = (float(bbox[0]) + float(bbox[2])) * 0.5
    except (TypeError, ValueError, IndexError):
        x_center = 0.0
    if frame_width <= 0:
        return 0.5
    return max(0.0, min(1.0, x_center / float(frame_width)))


def item_from_detection(detection: dict, frame_width: int) -> LcdItem:
    label = sanitize_label(str(detection.get("class_name", "object")))
    confidence = float(detection.get("confidence", 0.0))
    return LcdItem(
        icon=icon_for_class(label),
        label=label,
        confidence=max(0.0, min(1.0, confidence)),
        x_center=detection_x_center(detection, frame_width),
    )


def state_from_detections(detections: list[dict], frame_width: int, max_items: int) -> LcdState:
    if not detections:
        return LcdState((), 0)

    max_items = max(1, min(5, max_items))
    items = [item_from_detection(detection, frame_width) for detection in detections]
    items.sort(key=lambda item: item.x_center)
    return LcdState(tuple(items[:max_items]), len(detections))


def lcd_state_summary(state: LcdState) -> str:
    if not state.items:
        return "idle"
    labels = ",".join(label_code(item.label) for item in state.items)
    overflow = state.total_count - len(state.items)
    return labels if overflow <= 0 else f"{labels},+{overflow}"


def adjusted_icon_centers(items: tuple[LcdItem, ...]) -> list[int]:
    if not items:
        return []

    left = 16
    right = WIDTH - 16
    targets = [left + round(item.x_center * (right - left)) for item in items]
    if len(targets) == 1:
        return [max(left, min(right, targets[0]))]

    min_sep = min(30, max(20, (right - left) // (len(targets) - 1)))
    centers = [max(left, min(right, targets[0]))]
    for target in targets[1:]:
        centers.append(max(max(left, min(right, target)), centers[-1] + min_sep))

    overflow = centers[-1] - right
    if overflow > 0:
        centers = [center - overflow for center in centers]

    if centers[0] < left:
        shift = left - centers[0]
        centers = [center + shift for center in centers]

    return [max(left, min(right, center)) for center in centers]


def draw_confidence_bar(pixels: list[int], cx: int, y: int, confidence: float, color: int) -> None:
    width = 22
    filled = max(1, min(width, round(width * confidence)))
    x = cx - width // 2
    for xx in range(x, x + width):
        set_pixel(pixels, xx, y, GRAY)
        set_pixel(pixels, xx, y + 1, GRAY)
    for xx in range(x, x + filled):
        set_pixel(pixels, xx, y, color)


def draw_mini_person(helper: ModuleType, pixels: list[int], cx: int, color: int) -> None:
    del helper
    draw_circle(pixels, cx, 29, 3, color, 1)
    draw_line(pixels, cx, 33, cx, 43, color, 2)
    draw_line(pixels, cx - 8, 37, cx + 8, 37, color, 2)
    draw_line(pixels, cx, 43, cx - 7, 53, color, 2)
    draw_line(pixels, cx, 43, cx + 7, 53, color, 2)


def draw_mini_vehicle(helper: ModuleType, pixels: list[int], cx: int, color: int) -> None:
    helper.draw_rect(pixels, cx - 11, 39, 22, 8, color)
    helper.draw_rect(pixels, cx - 7, 33, 14, 6, color)
    fill_circle(pixels, cx - 7, 49, 3, DARK)
    fill_circle(pixels, cx + 7, 49, 3, DARK)
    draw_circle(pixels, cx - 7, 49, 3, WHITE, 1)
    draw_circle(pixels, cx + 7, 49, 3, WHITE, 1)


def draw_mini_animal(helper: ModuleType, pixels: list[int], cx: int, color: int) -> None:
    helper.draw_rect(pixels, cx - 10, 38, 16, 8, color)
    fill_circle(pixels, cx + 9, 36, 5, color)
    draw_line(pixels, cx - 8, 46, cx - 8, 54, color, 2)
    draw_line(pixels, cx + 3, 46, cx + 3, 54, color, 2)
    draw_line(pixels, cx - 10, 39, cx - 15, 34, color, 1)
    set_pixel(pixels, cx + 11, 35, DARK)


def draw_mini_food(helper: ModuleType, pixels: list[int], cx: int, color: int) -> None:
    del helper
    draw_line(pixels, cx - 12, 47, cx + 12, 47, color, 2)
    draw_line(pixels, cx - 8, 48, cx - 3, 54, color, 1)
    draw_line(pixels, cx + 8, 48, cx + 3, 54, color, 1)
    fill_circle(pixels, cx - 6, 39, 4, ORANGE)
    fill_circle(pixels, cx + 1, 37, 4, GREEN)
    fill_circle(pixels, cx + 8, 40, 4, RED)


def draw_mini_drink(helper: ModuleType, pixels: list[int], cx: int, color: int) -> None:
    draw_box(helper, pixels, cx - 5, 33, 10, 21, color, 2)
    helper.draw_rect(pixels, cx - 3, 28, 6, 5, color)
    helper.draw_rect(pixels, cx - 4, 26, 8, 2, color)
    helper.draw_rect(pixels, cx - 3, 43, 6, 7, CYAN)


def draw_mini_screen(helper: ModuleType, pixels: list[int], cx: int, color: int) -> None:
    draw_box(helper, pixels, cx - 13, 33, 26, 16, color, 2)
    helper.draw_rect(pixels, cx - 9, 37, 18, 8, BLUE)
    draw_line(pixels, cx, 50, cx, 55, color, 2)
    draw_line(pixels, cx - 8, 56, cx + 8, 56, color, 2)


def draw_mini_furniture(helper: ModuleType, pixels: list[int], cx: int, color: int) -> None:
    helper.draw_rect(pixels, cx - 8, 32, 16, 5, color)
    helper.draw_rect(pixels, cx - 8, 37, 5, 17, color)
    helper.draw_rect(pixels, cx - 8, 46, 18, 5, color)
    draw_line(pixels, cx - 3, 51, cx - 5, 57, color, 2)
    draw_line(pixels, cx + 8, 51, cx + 10, 57, color, 2)


def draw_mini_object(helper: ModuleType, pixels: list[int], cx: int, color: int) -> None:
    draw_box(helper, pixels, cx - 8, 39, 16, 12, color, 2)
    draw_line(pixels, cx - 8, 39, cx - 2, 33, color, 1)
    draw_line(pixels, cx + 8, 39, cx + 14, 33, color, 1)
    draw_line(pixels, cx - 2, 33, cx + 14, 33, color, 1)


def draw_mini_icon(helper: ModuleType, pixels: list[int], item: LcdItem, cx: int) -> None:
    color = icon_color(item.icon)
    draw_funcs = {
        "person": draw_mini_person,
        "vehicle": draw_mini_vehicle,
        "animal": draw_mini_animal,
        "food": draw_mini_food,
        "drink": draw_mini_drink,
        "screen": draw_mini_screen,
        "furniture": draw_mini_furniture,
        "object": draw_mini_object,
    }
    draw_funcs.get(item.icon, draw_mini_object)(helper, pixels, cx, color)

    code = label_code(item.label)
    text_x = max(0, min(WIDTH - len(code) * 6, cx - len(code) * 3))
    helper.draw_text(pixels, text_x, 62, code, WHITE, 1)
    draw_confidence_bar(pixels, cx, 73, item.confidence, color)


def draw_idle(helper: ModuleType, pixels: list[int]) -> None:
    helper.draw_text(pixels, 55, 6, "IDLE", CYAN, 2)
    draw_circle(pixels, 80, 41, 16, CYAN, 2)
    draw_line(pixels, 92, 53, 108, 67, CYAN, 3)
    draw_circle(pixels, 80, 41, 5, GRAY, 2)
    helper.draw_text(pixels, 31, 69, "NO OBJECT", WHITE, 1)


def render_lcd_frame(helper: ModuleType, state: LcdState) -> list[int]:
    pixels = [BLACK] * (WIDTH * HEIGHT)
    helper.fill(pixels, BLACK)
    helper.draw_rect(pixels, 0, 0, WIDTH, HEIGHT, DARK)

    if not state.items:
        draw_idle(helper, pixels)
        return pixels

    helper.draw_text(pixels, 4, 5, "DETECTED", CYAN, 1)
    helper.draw_text(pixels, 118, 5, str(min(state.total_count, 99)), WHITE, 1)
    overflow = state.total_count - len(state.items)
    if overflow > 0:
        helper.draw_text(pixels, 136, 5, f"+{min(overflow, 9)}", YELLOW, 1)

    for item, cx in zip(state.items, adjusted_icon_centers(state.items)):
        draw_mini_icon(helper, pixels, item, cx)

    return pixels


class LcdNotifier:
    def __init__(self, config: LcdConfig, helper: ModuleType | None = None) -> None:
        self.config = config
        self.helper = helper or load_lcd_helper()
        self.lcd = None
        self.last_key: tuple[object, ...] | None = None
        self.last_flush = 0.0
        self.queue: queue.Queue[tuple[LcdState, bool] | None] = queue.Queue(maxsize=1)
        self.thread: threading.Thread | None = None

    def open(self) -> None:
        self.lcd = self.helper.LcdSt7735(
            self.config.spi,
            self.config.reset_line,
            self.config.dc_line,
            self.config.gpio_mode,
            self.config.speed_hz,
        )
        self.lcd.init()
        self.thread = threading.Thread(target=self._worker, name="vim-5-yolo-lcd", daemon=True)
        self.thread.start()

    def close(self) -> None:
        if self.thread is not None:
            self._put_latest(None)
            self.thread.join()
            self.thread = None
        if self.lcd is not None:
            self.lcd.close()
            self.lcd = None

    def _put_latest(self, item: tuple[LcdState, bool] | None) -> None:
        try:
            self.queue.put_nowait(item)
            return
        except queue.Full:
            pass

        try:
            self.queue.get_nowait()
        except queue.Empty:
            pass
        self.queue.put_nowait(item)

    def _worker(self) -> None:
        while True:
            item = self.queue.get()
            if item is None:
                return
            state, force = item

            if not force:
                delay = self.config.refresh_interval - (time.time() - self.last_flush)
                if delay > 0:
                    time.sleep(delay)

            while True:
                try:
                    newer = self.queue.get_nowait()
                except queue.Empty:
                    break
                if newer is None:
                    return
                state, force = newer

            if self.lcd is None:
                continue
            self.lcd.flush(render_lcd_frame(self.helper, state))
            self.last_flush = time.time()

    def show(self, state: LcdState, force: bool = False) -> bool:
        if self.lcd is None:
            return False
        if not force and state.key == self.last_key:
            return False
        self.last_key = state.key
        self._put_latest((state, force))
        return True
