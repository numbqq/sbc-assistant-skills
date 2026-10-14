import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
NAME = "khadas-vim-5-app-launch"


class PortableInstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="portable skills ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "device sources"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts/install.sh", self.repo / "scripts/install.sh")
        shutil.copytree(ROOT / "skills/vim-5/app-launch", self.repo / "skills/vim-5/app-launch")
        self.platform = self.base / "arbitrary platform name"
        (self.platform / "runtime").mkdir(parents=True)
        (self.platform / "runtime/control-app").write_text(
            "import json,os,sys; print(json.dumps([os.environ['VIBE_ROOT'],sys.argv[1:]]))\n")
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("PICOCLAW_", "VIBE_", "CODEX_"))}
        self.env["HOME"] = str(self.base / "alice")
        self.home = self.base / "custom data"
        self.env["PICOCLAW_HOME"] = str(self.home)

    def install(self, *args):
        return subprocess.run(["bash", str(self.repo / "scripts/install.sh"), "--tool", "picoclaw",
                               "--skill", NAME, *args], env=self.env, cwd=self.base,
                              text=True, capture_output=True)

    def test_workspace_config_env_and_cli_precedence(self):
        config = self.base / "settings/config.json"
        config.parent.mkdir()
        configured = self.base / "configured workspace"
        config.write_text(json.dumps({"agents": {"defaults": {"workspace": str(configured)}}}))
        self.env["PICOCLAW_CONFIG"] = str(config)
        env_workspace = self.base / "environment workspace"
        cli_workspace = self.base / "cli workspace"
        for workspace, args in ((configured, ()), (env_workspace, ()),
                                (cli_workspace, ("--workspace", str(cli_workspace)))):
            if workspace == env_workspace:
                self.env["PICOCLAW_AGENTS_DEFAULTS_WORKSPACE"] = str(env_workspace)
            result = self.install(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((workspace / "skills" / NAME / "scripts/control-app").is_file())

    def test_config_location_does_not_move_default_workspace(self):
        config = self.base / "elsewhere.json"
        config.write_text("{}")
        self.env["PICOCLAW_CONFIG"] = str(config)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.home / "workspace/skills" / NAME / "SKILL.md").is_file())

    def test_binding_delegation_override_and_internal_generation(self):
        result = self.install("--platform-root", str(self.platform))
        self.assertEqual(result.returncode, 0, result.stderr)
        wrapper = self.home / "workspace/skills" / NAME / "scripts/control-app"
        command = [sys.executable, str(wrapper), "generate", "--prompt", "创建 飞机 $(literal)"]
        result = subprocess.run(command, env=self.env, cwd=self.base, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [str(self.platform), command[2:]])
        resolved = subprocess.run([sys.executable, str(wrapper), "--print-platform-root"],
                                  env=self.env, cwd=self.base, text=True, capture_output=True)
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        self.assertEqual(resolved.stdout.strip(), str(self.platform))
        for variable, value in (("VIBE_ROOT", str(self.base / "missing")),
                                ("VIBE_PICOCLAW_INTERNAL_GENERATION", "1")):
            result = subprocess.run(command, env=dict(self.env, **{variable: value}),
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")

    def test_openclaw_converted_skill_has_usable_binding(self):
        shutil.copy2(ROOT / "scripts/convert.sh", self.repo / "scripts/convert.sh")
        result = subprocess.run(["bash", str(self.repo / "scripts/convert.sh"),
                                 "--tool", "openclaw", "--skill", NAME],
                                env=self.env, cwd=self.base, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.base / "custom agents"
        env = dict(self.env, OPENCLAW_AGENTS_DIR=str(target))
        result = subprocess.run(["bash", str(self.repo / "scripts/install.sh"), "--tool", "openclaw",
                                 "--skill", NAME, "--platform-root", str(self.platform)],
                                env=env, cwd=self.base, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        wrapper = target / NAME / "skill/scripts/control-app"
        result = subprocess.run([sys.executable, str(wrapper), "--print-platform-root"],
                                env=env, cwd=self.base, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.platform))

    def test_unbound_install_discovers_selected_hook_from_unrelated_cwd(self):
        config = self.base / "selected.json"
        config.write_text(json.dumps({"hooks": {"processes": {"vibe_creation_loader": {
            "env": {"VIBE_ROOT": str(self.platform)}}}}}))
        self.env["PICOCLAW_CONFIG"] = str(config)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        wrapper = self.home / "workspace/skills" / NAME / "scripts/control-app"
        result = subprocess.run([sys.executable, str(wrapper), "catalog"], env=self.env,
                                cwd=self.base, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), [str(self.platform), ["catalog"]])

    def test_invalid_config_and_conflicting_local_do_not_report_success(self):
        config = self.base / "broken.json"
        config.write_text("{")
        self.env["PICOCLAW_CONFIG"] = str(config)
        self.assertNotEqual(self.install().returncode, 0)
        self.assertNotEqual(self.install("--workspace", str(self.base), "--local").returncode, 0)


class CrossSkillPathsTests(unittest.TestCase):
    def test_source_installed_openclaw_and_explicit_override(self):
        helper = ROOT / "skills/vim-5/npu/scripts/vim_5_skill_paths.py"
        spec = importlib.util.spec_from_file_location("portable_skill_paths", helper)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix="skill siblings ") as directory:
            root = Path(directory)
            for npu, hardware in (("npu", "hardware-control"),
                                  ("khadas-vim-5-npu", "khadas-vim-5-hardware-control"),
                                  ("khadas-vim-5-npu/skill", "khadas-vim-5-hardware-control/skill")):
                target = root / hardware / "scripts/spi_lcd_st7735.py"
                with patch.dict(os.environ, {}, clear=True):
                    self.assertIn(target, module.lcd_helper_candidates(root / npu))
            with patch.dict(os.environ, {"VIBE_SPI_LCD_HELPER": str(root / "explicit.py")}, clear=True):
                self.assertEqual(module.lcd_helper_candidates(root / "npu"), [root / "explicit.py"])
