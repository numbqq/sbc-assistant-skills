import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "install.sh"
CONVERT = ROOT / "scripts" / "convert.sh"
SKILL_NAME = "khadas-vim-5-hardware-control"


def run_script(script: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        ["bash", str(script), *args],
        cwd=ROOT,
        env=merged_env,
        text=True,
        capture_output=True,
        check=False,
    )


class InstallToolSupportTest(unittest.TestCase):
    def test_install_list_tools_includes_picoclaw(self):
        result = run_script(INSTALL, "--list-tools")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("picoclaw", result.stdout.splitlines())

    def test_convert_list_tools_includes_picoclaw(self):
        result = run_script(CONVERT, "--list-tools")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("picoclaw", result.stdout.splitlines())

    def test_install_picoclaw_dry_run_uses_workspace_skills_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            result = run_script(
                INSTALL,
                "--tool",
                "picoclaw",
                "--skill",
                SKILL_NAME,
                "--dry-run",
                env={"HOME": str(home)},
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(".picoclaw/workspace/skills", result.stdout)
        self.assertIn(SKILL_NAME, result.stdout)

    def test_install_picoclaw_local_uses_repo_workspace_skills_path(self):
        result = run_script(
            INSTALL,
            "--tool",
            "picoclaw",
            "--skill",
            SKILL_NAME,
            "--dry-run",
            "--local",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(ROOT / ".picoclaw" / "workspace" / "skills"), result.stdout)

    def test_convert_picoclaw_reports_native_install_command(self):
        result = run_script(CONVERT, "--tool", "picoclaw", "--skill", SKILL_NAME)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"native=picoclaw:{SKILL_NAME}", result.stdout)
        self.assertIn(f"run: {ROOT}/scripts/install.sh --tool picoclaw --skill {SKILL_NAME}", result.stdout)


if __name__ == "__main__":
    unittest.main()
