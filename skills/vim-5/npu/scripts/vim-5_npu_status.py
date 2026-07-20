#!/usr/bin/env python3
"""Inspect VIM 5 NPU skill readiness and print reusable YOLOv8n commands."""

from __future__ import annotations

import argparse
import glob
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONDA_ENV = "amlnnlite_py310"
WHEEL_GLOB = "amlnn_edge_toolkit_lite-*-linux_aarch64.whl"

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = SKILL_ROOT / "scripts"
ASSET_ROOT = SKILL_ROOT / "assets"
BUNDLED_ADLA_MODEL = ASSET_ROOT / "yolov8n" / "model" / "yolov8n_rawhead_w8a8_a311y3.adla"
BUNDLED_IMAGE_DIR = ASSET_ROOT / "yolov8n" / "input"
BUNDLED_TEST_IMAGE = BUNDLED_IMAGE_DIR / "test_image.png"
CORE_MODULE = SCRIPT_DIR / "vim_5_yolov8n_core.py"
IMAGE_SCRIPT = SCRIPT_DIR / "vim-5_yolov8n_image.py"
USB_CAMERA_SCRIPT = SCRIPT_DIR / "vim-5_yolov8n_usb_camera.py"

COMMON_CONDA_PATHS = (
    Path.home() / "miniforge3" / "bin" / "conda",
    Path.home() / "miniforge3" / "condabin" / "conda",
    Path.home() / "miniconda3" / "bin" / "conda",
    Path.home() / "miniconda3" / "condabin" / "conda",
    Path.home() / "anaconda3" / "bin" / "conda",
    Path.home() / "anaconda3" / "condabin" / "conda",
    Path("/opt/conda/bin/conda"),
)


@dataclass(frozen=True)
class PathCheck:
    name: str
    path: Path
    ready: bool


def q(value: object) -> str:
    return shlex.quote(str(value))


def command_exists(command: str) -> bool:
    if "/" in command:
        return os.access(command, os.X_OK)
    return shutil.which(command) is not None


def conda_command(args: argparse.Namespace) -> str:
    if getattr(args, "conda", ""):
        return args.conda

    path = shutil.which("conda")
    if path:
        return path

    for candidate in COMMON_CONDA_PATHS:
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)

    return "conda"


def conda_command_state(args: argparse.Namespace) -> str:
    command = conda_command(args)
    if command_exists(command):
        return f"present:{command}"
    return f"missing:{command}"


def conda_profile_script(args: argparse.Namespace) -> Path | None:
    command = conda_command(args)
    if "/" not in command:
        return None

    bin_dir = Path(command).resolve().parent
    root = bin_dir.parent if bin_dir.name in {"bin", "condabin"} else bin_dir
    profile = root / "etc" / "profile.d" / "conda.sh"
    return profile if profile.exists() else None


def run_check(args: list[str], timeout: float = 15.0) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            args,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode == 0, output


def compact_output(output: str) -> str:
    return " ".join(line.strip() for line in output.splitlines() if line.strip())


def target_python_args(args: argparse.Namespace) -> list[str]:
    if getattr(args, "python", ""):
        return shlex.split(args.python)
    return [conda_command(args), "run", "-n", args.conda_env, "python"]


def target_python_text(args: argparse.Namespace) -> str:
    return " ".join(q(part) for part in target_python_args(args))


def target_python_module_state(args: argparse.Namespace, module: str) -> str:
    ok, output = run_check(target_python_args(args) + ["-c", f"import {module}; print('present')"])
    if ok:
        return "present"
    output = compact_output(output)
    return "missing" + (f":{output}" if output else "")


def target_python_executable(args: argparse.Namespace) -> str:
    ok, output = run_check(target_python_args(args) + ["-c", "import sys; print(sys.executable)"])
    if ok and output:
        return output.splitlines()[-1]
    output = compact_output(output)
    return "missing" + (f":{output}" if output else "")


def npu_runtime_probe(args: argparse.Namespace, model_path: Path) -> str:
    if not model_path.exists():
        return f"missing:model not found: {model_path}"

    code = f"""
from amlnnlite.api import AMLNNLite as AMLNN
amlnn = AMLNN()
runtime_ready = False
try:
    amlnn.init_runtime(mode="native", enable_perf=False)
    runtime_ready = True
    amlnn.load_model(path={str(model_path)!r})
    print("present")
finally:
    if runtime_ready:
        amlnn.uninit()
"""
    ok, output = run_check(target_python_args(args) + ["-c", code], timeout=30.0)
    if ok:
        return "present"
    output = compact_output(output)
    return "missing" + (f":{output}" if output else "")


def path_check(name: str, path: Path) -> PathCheck:
    return PathCheck(name=name, path=path, ready=path.exists())


def image_files(image_dir: Path) -> list[Path]:
    patterns = ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.JPG", "*.JPEG", "*.PNG", "*.BMP")
    files: list[Path] = []
    if image_dir.exists():
        for pattern in patterns:
            files.extend(image_dir.glob(pattern))
    return sorted(path for path in files if path.is_file())


def video_devices() -> list[str]:
    return sorted(glob.glob("/dev/video*"))


def adla_device_nodes() -> list[str]:
    return sorted(glob.glob("/dev/adla*"))


def adla_sysfs_devices() -> list[str]:
    return sorted(glob.glob("/sys/class/adla/adla*"))


def requirement_files(setup_dir: Path) -> list[Path]:
    return sorted(setup_dir.rglob("requirements.txt")) if setup_dir.exists() else []


def toolkit_wheels(setup_dir: Path) -> list[Path]:
    return sorted(setup_dir.rglob(WHEEL_GLOB)) if setup_dir.exists() else []


def joined_paths(paths: list[Path]) -> str:
    return " ".join(str(path) for path in paths) if paths else "none"


def selected_model_path(args: argparse.Namespace) -> Path:
    return args.model_path or BUNDLED_ADLA_MODEL


def selected_image_dir(args: argparse.Namespace) -> Path:
    return args.image_dir or BUNDLED_IMAGE_DIR


def setup_command_lines(args: argparse.Namespace) -> list[str]:
    setup_dir = args.setup_dir or Path(".")
    requirements = args.requirements or setup_dir / "requirements.txt"
    wheel_pattern = args.wheel or setup_dir / WHEEL_GLOB
    lines = []
    profile = conda_profile_script(args)
    if profile is not None:
        lines.append(f"source {q(profile)}")
    lines.extend(
        [
            f"{q(conda_command(args))} create -n {q(args.conda_env)} python=3.10 -y",
            f"conda activate {q(args.conda_env)}",
            f"cd {q(setup_dir)}",
            f"for req in $(cat {q(requirements)}); do pip install $req; done",
            f"pip install opencv-python {wheel_pattern}",
        ]
    )
    return lines


def cmd_setup_commands(args: argparse.Namespace) -> int:
    for line in setup_command_lines(args):
        print(line)
    return 0


def cmd_image(args: argparse.Namespace) -> str:
    parts = [
        target_python_text(args),
        q(IMAGE_SCRIPT),
        "--model-path",
        q(selected_model_path(args)),
        "--image-dir",
        q(selected_image_dir(args)),
        "--output-dir",
        q(args.output_dir),
        "--conf",
        q(args.conf),
        "--nms",
        q(args.nms),
    ]
    if args.perf_visualize:
        parts.append("--perf-visualize")
    return " ".join(parts)


def cmd_usb(args: argparse.Namespace) -> str:
    parts = [
        target_python_text(args),
        q(USB_CAMERA_SCRIPT),
        "--model-path",
        q(selected_model_path(args)),
        "--camera",
        q(args.camera),
        "--width",
        q(args.width),
        "--height",
        q(args.height),
        "--fps",
        q(args.fps),
        "--fourcc",
        q(args.fourcc),
        "--conf",
        q(args.conf),
        "--nms",
        q(args.nms),
        "--display",
        q(args.display),
    ]
    if args.max_frames > 0:
        parts.extend(["--max-frames", q(args.max_frames)])
    if args.output:
        parts.extend(["--output", q(args.output)])
    return " ".join(parts)


def print_path_checks() -> None:
    checks = [
        path_check("skill_root", SKILL_ROOT),
        path_check("core_module", CORE_MODULE),
        path_check("image_script", IMAGE_SCRIPT),
        path_check("usb_camera_script", USB_CAMERA_SCRIPT),
        path_check("bundled_adla_model", BUNDLED_ADLA_MODEL),
        path_check("bundled_image_dir", BUNDLED_IMAGE_DIR),
        path_check("bundled_test_image", BUNDLED_TEST_IMAGE),
    ]
    for check in checks:
        print(f"{check.name}={'ready' if check.ready else 'missing'}:{check.path}")


def cmd_status(args: argparse.Namespace) -> int:
    print("board=Khadas VIM 5")
    print("npu=8_TOPS")
    print(f"checker_python_executable={sys.executable}")
    print("conda_command=" + conda_command_state(args))
    print(f"target_conda_env={args.conda_env}")
    print("target_python_command=" + target_python_text(args))
    print("target_python_executable=" + target_python_executable(args))

    runtime_state = target_python_module_state(args, "amlnnlite")
    cv2_state = target_python_module_state(args, "cv2")
    numpy_state = target_python_module_state(args, "numpy")
    print("runtime_module_amlnnlite=" + runtime_state)
    print("module_cv2=" + cv2_state)
    print("module_numpy=" + numpy_state)

    print_path_checks()
    model_path = selected_model_path(args)
    image_dir = selected_image_dir(args)
    files = image_files(image_dir)
    probe_state = npu_runtime_probe(args, model_path)
    print(f"selected_model_path={model_path}")
    print(f"selected_image_dir={image_dir}")
    print("selected_images=" + joined_paths(files))
    print("npu_runtime_probe=" + probe_state)

    setup_dir = args.setup_dir or Path(".")
    requirements = requirement_files(setup_dir)
    wheels = toolkit_wheels(setup_dir)
    print(f"setup_dir={setup_dir}")
    print("requirements_files=" + joined_paths(requirements))
    print("amlnn_lite_wheels=" + joined_paths(wheels))

    devices = video_devices()
    adla_nodes = adla_device_nodes()
    adla_sysfs = adla_sysfs_devices()
    print("video_devices=" + (" ".join(devices) if devices else "none"))
    print("adla_device_nodes=" + (" ".join(adla_nodes) if adla_nodes else "none"))
    print("adla_sysfs_devices=" + (" ".join(adla_sysfs) if adla_sysfs else "none"))

    deps_ready = runtime_state == "present" and cv2_state == "present" and numpy_state == "present"
    npu_ready = probe_state == "present"
    model_ready = model_path.exists()
    image_ready = bool(files)
    image_script_ready = IMAGE_SCRIPT.exists()
    usb_camera_script_ready = USB_CAMERA_SCRIPT.exists()
    camera_ready = bool(devices)
    print(f"yolov8n_image_ready={'yes' if deps_ready and npu_ready and model_ready and image_ready and image_script_ready else 'no'}")
    print(f"yolov8n_usb_camera_ready={'yes' if deps_ready and npu_ready and model_ready and usb_camera_script_ready and camera_ready else 'no'}")

    if runtime_state.startswith("missing"):
        print(f"missing_runtime_note=create/activate conda env {args.conda_env} and install amlnn_edge_toolkit_lite wheel")
    if cv2_state.startswith("missing"):
        print(f"missing_cv2_note=install opencv-python inside conda env {args.conda_env}")
    if not model_ready:
        print(f"missing_model_note=expected bundled or user-provided ADLA model at {model_path}")
    if not npu_ready:
        print("missing_npu_runtime_note=AMLNNLite could not initialize the ADLA runtime and load the model")
    if not adla_nodes:
        print("missing_adla_device_note=no /dev/adla* device node is visible in this execution environment")
    if adla_sysfs and not adla_nodes:
        print("adla_device_visibility_note=sysfs reports ADLA, but /dev/adla* is not visible; rerun status from a shell that has hardware device access")
    if not image_ready:
        print(f"missing_image_note=expected at least one image under {image_dir}")
    if not image_script_ready:
        print(f"missing_image_script_note=expected bundled image script at {IMAGE_SCRIPT}")
    if not usb_camera_script_ready:
        print(f"missing_usb_camera_script_note=expected bundled USB camera script at {USB_CAMERA_SCRIPT}")
    if not requirements:
        print("missing_requirements_note=no requirements.txt found under setup dir; pass --setup-dir or --requirements for the SDK/package directory")
    if not wheels:
        print("missing_wheel_note=no amlnn_edge_toolkit_lite wheel found under setup dir; pass --setup-dir or --wheel for the SDK/package directory")
    if not camera_ready:
        print("missing_camera_note=no /dev/video* devices found")
    return 0


def cmd_commands(args: argparse.Namespace) -> int:
    print("setup_commands_begin")
    for line in setup_command_lines(args):
        print(line)
    print("setup_commands_end")
    print("image_command=" + cmd_image(args))
    print("usb_camera_command=" + cmd_usb(args))
    return 0


def add_runtime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--conda-env", default=DEFAULT_CONDA_ENV)
    parser.add_argument("--conda", default="", help="Override conda executable; default auto-detects common installs")
    parser.add_argument("--python", default="", help="Override Python command; default uses conda run")


def add_setup_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--setup-dir", type=Path, default=None)
    parser.add_argument("--requirements", type=Path, default=None)
    parser.add_argument("--wheel", type=Path, default=None)


def add_inference_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--model-path", type=Path, default=None)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--nms", type=float, default=0.4)


def add_image_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--image-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("yolov8n_result"))
    parser.add_argument("--perf-visualize", action="store_true")


def add_usb_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--camera", default="/dev/video0")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--fourcc", default="MJPG")
    parser.add_argument("--display", choices=("auto", "on", "off"), default="auto")
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--output", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="print VIM 5 NPU skill status")
    add_runtime_args(status)
    add_setup_args(status)
    add_inference_args(status)
    add_image_args(status)
    status.set_defaults(func=cmd_status)

    setup = subparsers.add_parser("setup-commands", help="print conda setup commands for the VIM 5 NPU Python environment")
    add_runtime_args(setup)
    add_setup_args(setup)
    setup.set_defaults(func=cmd_setup_commands)

    commands = subparsers.add_parser("commands", help="print setup, image, and USB camera commands")
    add_runtime_args(commands)
    add_setup_args(commands)
    add_inference_args(commands)
    add_image_args(commands)
    add_usb_args(commands)
    commands.set_defaults(func=cmd_commands)

    image = subparsers.add_parser("image-command", help="print the bundled YOLOv8n image inference command")
    add_runtime_args(image)
    add_inference_args(image)
    add_image_args(image)
    image.set_defaults(func=lambda args: print(cmd_image(args)) or 0)

    usb = subparsers.add_parser("usb-camera-command", help="print the bundled YOLOv8n USB camera command")
    add_runtime_args(usb)
    add_inference_args(usb)
    add_usb_args(usb)
    usb.set_defaults(func=lambda args: print(cmd_usb(args)) or 0)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
