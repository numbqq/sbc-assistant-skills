import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
NAME = "khadas-vim-5-npu"


class NPUModelInstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="npu install space ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/install.sh", self.root / "scripts/install.sh")
        self.source = self.root / "skills/vim-5/npu"
        assets = self.source / "assets/aml-asr"
        self.model = assets / "model"
        self.model.mkdir(parents=True)
        (self.source / "SKILL.md").write_text(f"---\nname: {NAME}\ndescription: fixture\n---\n")
        shutil.copy2(ROOT / "skills/vim-5/npu/assets/aml-asr/assemble-model.sh", assets / "assemble-model.sh")
        self.contents = b""
        manifest = []
        for i in range(10):
            name = f"asr123_v1p3.nb.part{i:02d}"
            contents = f"fixture part {i}".encode()
            (self.model / name).write_bytes(contents)
            manifest.append(f"{hashlib.sha256(contents).hexdigest()}  {name}\n")
            self.contents += contents
        (self.model / "PARTS_SHA256SUMS.txt").write_text("".join(manifest))
        (self.model / "MODEL_SHA256SUMS.txt").write_text(
            f"{hashlib.sha256(self.contents).hexdigest()}  asr123_v1p3.nb\n")
        self.target_root = self.root / "target"
        self.target = self.target_root / "workspace/skills" / NAME

    def run_install(self, *args, tool="picoclaw", env=None):
        return subprocess.run(["bash", str(self.root / "scripts/install.sh"), "--tool", tool,
            "--skill", NAME, *args], cwd=self.root, capture_output=True, text=True,
            env=dict(os.environ, PICOCLAW_HOME=str(self.target_root), **(env or {})))

    def assert_no_staging(self, directory):
        self.assertEqual(list(directory.glob(".khadas-vim-5-npu.install.*")), [])

    def test_install_and_reinstall_create_verified_model_without_changing_source(self):
        for _ in range(2):
            result = self.run_install()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((self.target / "assets/aml-asr/model/asr123_v1p3.nb").read_bytes(), self.contents)
            self.assertIn(f"installed={self.target}", result.stdout)
            self.assert_no_staging(self.target.parent)
        self.assertFalse((self.model / "asr123_v1p3.nb").exists())

    def test_missing_or_bad_part_keeps_existing_skill_and_returns_failure(self):
        self.target.mkdir(parents=True)
        (self.target / "previous").write_text("working installation")
        part = self.model / "asr123_v1p3.nb.part03"
        part.write_bytes(b"corrupt")
        for state in ("corrupt", "missing"):
            if state == "missing":
                part.unlink()
            result = self.run_install()
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((self.target / "previous").read_text(), "working installation")
            self.assertNotIn("installed=", result.stdout)
            self.assert_no_staging(self.target.parent)

    def test_dry_run_does_not_copy_or_assemble_even_with_invalid_parts(self):
        (self.model / "asr123_v1p3.nb.part03").unlink()
        result = self.run_install("--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.target_root.exists())
        self.assertFalse((self.model / "asr123_v1p3.nb").exists())

    def test_codex_and_local_picoclaw_installation_prepare_model(self):
        codex_root = self.root / "codex"
        result = self.run_install(tool="codex", env={"CODEX_HOME": str(codex_root)})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((codex_root / "skills" / NAME / "assets/aml-asr/model/asr123_v1p3.nb").read_bytes(), self.contents)
        result = self.run_install("--local")
        self.assertEqual(result.returncode, 0, result.stderr)
        local = self.root / ".picoclaw/workspace/skills" / NAME
        self.assertEqual((local / "assets/aml-asr/model/asr123_v1p3.nb").read_bytes(), self.contents)

    def test_openclaw_prepares_model_inside_converted_skill(self):
        converted = self.root / "integrations/openclaw/agents" / NAME
        converted.mkdir(parents=True)
        shutil.copytree(self.source, converted / "skill")
        (converted / "AGENTS.md").write_text("converted agent")
        target_root = self.root / "openclaw"
        result = self.run_install(tool="openclaw", env={"OPENCLAW_AGENTS_DIR": str(target_root)})
        self.assertEqual(result.returncode, 0, result.stderr)
        target = target_root / NAME
        self.assertEqual((target / "skill/assets/aml-asr/model/asr123_v1p3.nb").read_bytes(), self.contents)
        self.assertEqual((target / "AGENTS.md").read_text(), "converted agent")
        self.assert_no_staging(target_root)


if __name__ == "__main__":
    unittest.main()
