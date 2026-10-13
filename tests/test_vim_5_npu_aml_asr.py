import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "skills/vim-5/npu/assets/aml-asr"


class AMLASRAssetsTests(unittest.TestCase):
    def test_bundled_runtime_is_arm64_and_manifest_verifies(self):
        executable = ASSETS / "bin/asr_realtime"
        header = executable.read_bytes()[:20]
        self.assertEqual(header[:5], b"\x7fELF\x02")
        self.assertEqual(struct.unpack("<H", header[18:20])[0], 183)
        self.assertTrue(os.access(executable, os.X_OK))
        result = subprocess.run(["sha256sum", "-c", "SHA256SUMS.txt"], cwd=ASSETS,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_model_assembly_verifies_parts_and_refuses_bad_existing_model(self):
        with tempfile.TemporaryDirectory(prefix="aml model space ") as temporary:
            root = Path(temporary)
            model = root / "model"
            model.mkdir()
            script = root / "assemble-model.sh"
            shutil.copy2(ASSETS / script.name, script)
            parts, assembled = [], b""
            for index in range(10):
                data = f"model part {index}".encode()
                name = f"asr123_v1p3.nb.part{index:02d}"
                (model / name).write_bytes(data)
                parts.append(f"{hashlib.sha256(data).hexdigest()}  {name}\n")
                assembled += data
            (model / "PARTS_SHA256SUMS.txt").write_text("".join(parts))
            (model / "MODEL_SHA256SUMS.txt").write_text(f"{hashlib.sha256(assembled).hexdigest()}  asr123_v1p3.nb\n")
            def run():
                return subprocess.run(["bash", str(script)], capture_output=True, text=True)
            self.assertEqual(run().returncode, 0)
            target = model / "asr123_v1p3.nb"
            self.assertEqual(target.read_bytes(), assembled)
            self.assertEqual(run().returncode, 0)
            target.write_bytes(b"corrupt existing model")
            self.assertNotEqual(run().returncode, 0)
            self.assertEqual(target.read_bytes(), b"corrupt existing model")
            target.unlink()
            (model / "asr123_v1p3.nb.part01").write_bytes(b"bad part")
            self.assertNotEqual(run().returncode, 0)
            self.assertFalse(target.exists())
            self.assertEqual(list(model.glob(".assemble.*")), [])

    def test_wrapper_resolves_installed_paths_and_preserves_arguments(self):
        with tempfile.TemporaryDirectory(prefix="aml skill space ") as temporary:
            root = Path(temporary)
            (root / "bin").mkdir()
            shutil.copy2(ASSETS / "run.sh", root / "run.sh")
            binary = root / "bin/asr_realtime"
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "$LD_LIBRARY_PATH" "$@"\n')
            binary.chmod(0o755)
            result = subprocess.run(["bash", str(root / "run.sh"), "--mic-channel", "2", "--language", "zh"],
                env=dict(os.environ, LD_LIBRARY_PATH="/other/lib"), cwd="/tmp", capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.splitlines(), [str(root / "lib") + ":/other/lib", "--model-dir",
                str(root / "model") + "/", "--mic-channel", "2", "--language", "zh"])


if __name__ == "__main__":
    unittest.main()
