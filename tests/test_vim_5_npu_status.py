import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


HELPER_PATH = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "vim-5"
    / "npu"
    / "scripts"
    / "vim-5_npu_status.py"
)

spec = importlib.util.spec_from_file_location("vim_5_npu_status", HELPER_PATH)
vim_5_npu_status = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = vim_5_npu_status
spec.loader.exec_module(vim_5_npu_status)


class VimFiveNpuStatusTest(unittest.TestCase):
    def test_usb_camera_command_uses_bundled_script_and_model(self):
        args = vim_5_npu_status.build_parser().parse_args(
            [
                "usb-camera-command",
                "--conda",
                "conda",
                "--camera",
                "/dev/video2",
                "--width",
                "1280",
                "--height",
                "720",
                "--display",
                "off",
                "--max-frames",
                "5",
            ]
        )

        command = vim_5_npu_status.cmd_usb(args)

        self.assertNotIn("npu_applications", command)
        self.assertIn("conda run -n amlnnlite_py310 python", command)
        self.assertIn(str(vim_5_npu_status.USB_CAMERA_SCRIPT), command)
        self.assertIn(f"--model-path {vim_5_npu_status.BUNDLED_ADLA_MODEL}", command)
        self.assertIn("--camera /dev/video2", command)
        self.assertIn("--width 1280", command)
        self.assertIn("--height 720", command)
        self.assertIn("--display off", command)
        self.assertIn("--max-frames 5", command)

    def test_usb_camera_spi_lcd_command_names_camera_and_spi_lcd_explicitly(self):
        args = vim_5_npu_status.build_parser().parse_args(
            [
                "usb-camera-spi-lcd-command",
                "--conda",
                "conda",
                "--camera",
                "/dev/video2",
                "--width",
                "1280",
                "--height",
                "720",
                "--display",
                "off",
                "--max-frames",
                "5",
                "--lcd-max-items",
                "3",
                "--lcd-refresh",
                "0.25",
                "--spi",
                "/dev/spidev1.0",
            ]
        )

        command = vim_5_npu_status.cmd_usb_camera_spi_lcd(args)

        self.assertNotIn("usb" "_lcd", command)
        self.assertNotIn("npu_applications", command)
        self.assertIn("conda run -n amlnnlite_py310 python", command)
        self.assertIn(str(vim_5_npu_status.USB_CAMERA_SPI_LCD_SCRIPT), command)
        self.assertIn(f"--model-path {vim_5_npu_status.BUNDLED_ADLA_MODEL}", command)
        self.assertIn("--camera /dev/video2", command)
        self.assertIn("--width 1280", command)
        self.assertIn("--height 720", command)
        self.assertIn("--display off", command)
        self.assertIn("--max-frames 5", command)
        self.assertIn("--lcd on", command)
        self.assertIn("--lcd-max-items 3", command)
        self.assertIn("--lcd-refresh 0.25", command)
        self.assertIn("--spi /dev/spidev1.0", command)

    def test_image_command_uses_bundled_script_assets_and_output_dir(self):
        args = vim_5_npu_status.build_parser().parse_args(
            ["image-command", "--conda", "conda", "--output-dir", "/tmp/out"]
        )

        command = vim_5_npu_status.cmd_image(args)

        self.assertNotIn("npu_applications", command)
        self.assertIn("conda run -n amlnnlite_py310 python", command)
        self.assertIn(str(vim_5_npu_status.IMAGE_SCRIPT), command)
        self.assertIn(f"--model-path {vim_5_npu_status.BUNDLED_ADLA_MODEL}", command)
        self.assertIn(f"--image-dir {vim_5_npu_status.BUNDLED_IMAGE_DIR}", command)
        self.assertIn("--output-dir /tmp/out", command)

    def test_image_command_accepts_user_assets_without_app_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "custom.adla"
            image_dir = root / "images"
            model.touch()
            image_dir.mkdir()
            args = vim_5_npu_status.build_parser().parse_args(
                [
                    "image-command",
                    "--conda",
                    "conda",
                    "--model-path",
                    str(model),
                    "--image-dir",
                    str(image_dir),
                ]
            )

            command = vim_5_npu_status.cmd_image(args)

        self.assertIn(f"--model-path {model}", command)
        self.assertIn(f"--image-dir {image_dir}", command)

    def test_whisper_file_command_uses_bundled_assets_and_auto_language(self):
        args = vim_5_npu_status.build_parser().parse_args(
            [
                "whisper-file-command",
                "--conda",
                "conda",
                "--audio-file",
                "/tmp/speech.wav",
            ]
        )

        command = vim_5_npu_status.cmd_whisper_file(args)

        self.assertIn("conda run -n amlnnlite_py310 python", command)
        self.assertIn(str(vim_5_npu_status.WHISPER_SCRIPT), command)
        self.assertIn(f"--enc {vim_5_npu_status.BUNDLED_WHISPER_ENCODER}", command)
        self.assertIn(f"--dec {vim_5_npu_status.BUNDLED_WHISPER_DECODER}", command)
        self.assertIn(f"--tokenizer {vim_5_npu_status.BUNDLED_WHISPER_TOKENIZER}", command)
        self.assertIn("--audio-file /tmp/speech.wav", command)
        self.assertIn("--language auto", command)

    def test_whisper_microphone_command_supports_analog_mic_parameters(self):
        args = vim_5_npu_status.build_parser().parse_args(
            [
                "whisper-microphone-command",
                "--conda",
                "conda",
                "--device",
                "hw:0,1",
                "--capture-rate",
                "44100",
                "--capture-channels",
                "2",
                "--mic-channel",
                "mix",
                "--language",
                "auto",
            ]
        )

        command = vim_5_npu_status.cmd_whisper_microphone(args)

        self.assertTrue(command.startswith(vim_5_npu_status.ANALOG_MIC_ROUTE_COMMAND))
        self.assertIn(" && conda run -n amlnnlite_py310 python", command)
        self.assertIn(str(vim_5_npu_status.WHISPER_SCRIPT), command)
        self.assertIn("--microphone", command)
        self.assertIn("--device hw:0,1", command)
        self.assertIn("--capture-rate 44100", command)
        self.assertIn("--capture-channels 2", command)
        self.assertIn("--mic-channel mix", command)
        self.assertIn("--language auto", command)

    def test_whisper_pdm_microphone_command_does_not_change_analog_route(self):
        args = vim_5_npu_status.build_parser().parse_args(
            ["whisper-microphone-command", "--conda", "conda"]
        )

        command = vim_5_npu_status.cmd_whisper_microphone(args)

        self.assertNotIn("amixer", command)
        self.assertIn("--device hw:0,3", command)
        self.assertIn("--capture-rate 48000", command)
        self.assertIn("--capture-channels 6", command)

    def test_overlay_state_requires_ext_board_codec(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "kvim-5.dtb.overlay.env"
            config.write_text(
                'fdt_overlays="uart_ao_e ext-board-codec" # enabled\n',
                encoding="utf-8",
            )
            present = vim_5_npu_status.overlay_state(
                config,
                vim_5_npu_status.ANALOG_MIC_REQUIRED_OVERLAY,
            )
            config.write_text("fdt_overlays=uart_ao_e\n", encoding="utf-8")
            missing = vim_5_npu_status.overlay_state(
                config,
                vim_5_npu_status.ANALOG_MIC_REQUIRED_OVERLAY,
            )

        self.assertEqual(present, "present")
        self.assertTrue(missing.startswith("missing:ext-board-codec"))

    def test_status_reports_bundled_assets_and_no_reference_path(self):
        args = vim_5_npu_status.build_parser().parse_args(["status", "--conda", "conda"])
        stream = io.StringIO()

        with (
            mock.patch.object(vim_5_npu_status, "target_python_executable", return_value="missing"),
            mock.patch.object(vim_5_npu_status, "target_python_module_state", return_value="missing"),
            mock.patch.object(vim_5_npu_status, "npu_runtime_probe", return_value="missing:adla device not found"),
            mock.patch.object(vim_5_npu_status, "video_devices", return_value=[]),
            mock.patch.object(vim_5_npu_status, "adla_device_nodes", return_value=["/dev/adla0"]),
            mock.patch.object(vim_5_npu_status, "adla_sysfs_devices", return_value=["/sys/class/adla/adla0"]),
            mock.patch.object(
                vim_5_npu_status,
                "overlay_state",
                return_value="missing:ext-board-codec is not configured",
            ),
            contextlib.redirect_stdout(stream),
        ):
            rc = vim_5_npu_status.cmd_status(args)

        text = stream.getvalue()
        self.assertEqual(rc, 0)
        self.assertNotIn("npu_applications", text)
        self.assertIn("board=Khadas VIM 5", text)
        self.assertIn("npu=8_TOPS", text)
        self.assertIn("runtime_module_amlnnlite=missing", text)
        self.assertIn(f"image_script=ready:{vim_5_npu_status.IMAGE_SCRIPT}", text)
        self.assertIn(f"usb_camera_script=ready:{vim_5_npu_status.USB_CAMERA_SCRIPT}", text)
        self.assertIn(f"usb_camera_spi_lcd_script=ready:{vim_5_npu_status.USB_CAMERA_SPI_LCD_SCRIPT}", text)
        self.assertIn(f"spi_lcd_module=ready:{vim_5_npu_status.SPI_LCD_MODULE}", text)
        self.assertIn(f"bundled_adla_model=ready:{vim_5_npu_status.BUNDLED_ADLA_MODEL}", text)
        self.assertIn(f"whisper_script=ready:{vim_5_npu_status.WHISPER_SCRIPT}", text)
        self.assertIn(
            f"bundled_whisper_demo=ready:{vim_5_npu_status.BUNDLED_WHISPER_DEMO}",
            text,
        )
        self.assertIn(
            f"bundled_whisper_data=ready:{vim_5_npu_status.BUNDLED_WHISPER_DATA}",
            text,
        )
        self.assertIn(
            "bundled_whisper_tokenizer_info=ready:"
            f"{vim_5_npu_status.BUNDLED_WHISPER_TOKENIZER_INFO}",
            text,
        )
        self.assertIn(
            f"bundled_whisper_encoder=ready:{vim_5_npu_status.BUNDLED_WHISPER_ENCODER}",
            text,
        )
        self.assertIn(
            f"bundled_whisper_decoder=ready:{vim_5_npu_status.BUNDLED_WHISPER_DECODER}",
            text,
        )
        self.assertIn("module_transformers=missing", text)
        self.assertIn("module_librosa=missing", text)
        self.assertIn(f"selected_model_path={vim_5_npu_status.BUNDLED_ADLA_MODEL}", text)
        self.assertIn("npu_runtime_probe=missing:adla device not found", text)
        self.assertIn("adla_device_nodes=/dev/adla0", text)
        self.assertIn("adla_sysfs_devices=/sys/class/adla/adla0", text)
        self.assertIn("target_conda_env=amlnnlite_py310", text)
        self.assertIn("missing_runtime_note=create/activate conda env amlnnlite_py310", text)
        self.assertIn("missing_npu_runtime_note=AMLNNLite could not initialize", text)
        self.assertIn("missing_camera_note=no /dev/video* devices found", text)
        self.assertIn("yolov8n_usb_camera_spi_lcd_ready=no", text)
        self.assertIn("whisper_file_ready=no", text)
        self.assertIn("whisper_microphone_ready=no", text)
        self.assertIn("picoclaw_local_voice_ready=", text)
        self.assertIn("analog_mic_required_overlay=ext-board-codec", text)
        self.assertIn(
            "analog_mic_route_command=amixer -c 0 cset name='TDMIN_B source select' 'tdmin_b'",
            text,
        )
        self.assertIn("whisper_analog_microphone_ready=no", text)
        self.assertIn("missing_analog_mic_overlay_note=set fdt_overlays=ext-board-codec", text)

    def test_setup_commands_match_amlnnlite_py310_install_flow(self):
        args = vim_5_npu_status.build_parser().parse_args(
            [
                "setup-commands",
                "--conda",
                "conda",
                "--setup-dir",
                "/sdk",
            ]
        )

        lines = vim_5_npu_status.setup_command_lines(args)

        self.assertEqual(lines[0], "conda create -n amlnnlite_py310 python=3.10 -y")
        self.assertIn("conda activate amlnnlite_py310", lines)
        self.assertIn("for req in $(cat /sdk/requirements.txt); do pip install $req; done", lines)
        self.assertIn("pip install transformers librosa", lines)
        self.assertIn("pip install opencv-python /sdk/amlnn_edge_toolkit_lite-*-linux_aarch64.whl", lines)

    def test_conda_auto_detects_common_install_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            conda = root / "bin" / "conda"
            profile = root / "etc" / "profile.d" / "conda.sh"
            conda.parent.mkdir(parents=True)
            profile.parent.mkdir(parents=True)
            conda.touch()
            conda.chmod(0o755)
            profile.touch()
            args = vim_5_npu_status.build_parser().parse_args(["setup-commands"])

            with (
                mock.patch.object(vim_5_npu_status.shutil, "which", return_value=None),
                mock.patch.object(vim_5_npu_status, "COMMON_CONDA_PATHS", (conda,)),
            ):
                lines = vim_5_npu_status.setup_command_lines(args)

        self.assertEqual(lines[0], f"source {profile}")
        self.assertEqual(lines[1], f"{conda} create -n amlnnlite_py310 python=3.10 -y")


if __name__ == "__main__":
    unittest.main()
