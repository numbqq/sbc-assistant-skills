"""Find hardware-control resources beside a source or installed NPU skill."""

import os
from pathlib import Path


def lcd_helper_candidates(skill_root):
    override = os.environ.get("VIBE_SPI_LCD_HELPER")
    if override:
        return [Path(override).expanduser()]
    parent = Path(skill_root).resolve().parent
    # OpenClaw nests resources one level below each agent directory.
    if Path(skill_root).name == "skill":
        parent = parent.parent
    relative = Path("scripts/spi_lcd_st7735.py")
    codex = Path(os.environ.get("CODEX_HOME") or "~/.codex").expanduser()
    return [
        parent / "hardware-control" / relative,
        parent / "khadas-vim-5-hardware-control" / relative,
        parent / "khadas-vim-5-hardware-control/skill" / relative,
        codex / "skills/khadas-vim-5-hardware-control" / relative,
    ]
