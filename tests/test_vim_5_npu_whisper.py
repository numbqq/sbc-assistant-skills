import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NPU_SKILL = ROOT / "skills" / "vim-5" / "npu"
WHISPER_SCRIPT = NPU_SKILL / "scripts" / "vim-5_whisper.py"
WHISPER_ASSETS = NPU_SKILL / "assets" / "whisper"


class VimFiveNpuWhisperTest(unittest.TestCase):
    def test_script_is_valid_python(self):
        source = WHISPER_SCRIPT.read_text(encoding="utf-8")
        compile(source, str(WHISPER_SCRIPT), "exec")

    def test_runtime_assets_are_bundled(self):
        encoder = WHISPER_ASSETS / "model" / "whisper_encoder_static_sim_w8a16.adla"
        decoder = WHISPER_ASSETS / "model" / "whisper_decoder_static_sim_w8a16.adla"
        tokenizer = WHISPER_ASSETS / "tokenizer"
        runtime = WHISPER_ASSETS / "bin" / "whisper_demo"
        data_bin = WHISPER_ASSETS / "data_bin"

        self.assertGreater(encoder.stat().st_size, 1_000_000)
        self.assertGreater(decoder.stat().st_size, 1_000_000)
        self.assertGreater(runtime.stat().st_size, 100_000)
        self.assertTrue(os.access(runtime, os.X_OK))
        self.assertTrue((data_bin / "data.bin").is_file())
        self.assertTrue((data_bin / "tokenizer_info.bin").is_file())
        self.assertTrue((tokenizer / "tokenizer.json").is_file())
        self.assertTrue((tokenizer / "preprocessor_config.json").is_file())
        self.assertTrue((WHISPER_ASSETS / "LICENSE.openai.txt").is_file())


if __name__ == "__main__":
    unittest.main()
