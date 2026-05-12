#!/usr/bin/env bash
set -euo pipefail

TOOL="codex"
DRY_RUN="no"

usage() {
  cat <<USAGE
Usage:
  $0 [--tool codex] [--dry-run]
  $0 --help

Options:
  --tool codex   Install the VIM4 hardware control skill for Codex.
  --dry-run      Print the planned install paths without copying files.
  --help         Show this help.
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --tool)
      TOOL="${2:?tool name required}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="yes"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

case "$TOOL" in
  codex) ;;
  *)
    echo "unsupported tool: $TOOL" >&2
    echo "currently supported tools: codex" >&2
    exit 1
    ;;
esac

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$REPO_ROOT/codex/vim4-hardware-control-skills"
CODEX_HOME_DIR="${CODEX_HOME:-$HOME/.codex}"
TARGET_ROOT="$CODEX_HOME_DIR/skills"
TARGET_DIR="$TARGET_ROOT/vim4-hardware-control-skills"

test -d "$SOURCE_DIR" || { echo "missing source skill: $SOURCE_DIR" >&2; exit 1; }
test -f "$SOURCE_DIR/SKILL.md" || { echo "missing skill file: $SOURCE_DIR/SKILL.md" >&2; exit 1; }

echo "tool=$TOOL"
echo "source=$SOURCE_DIR"
echo "target=$TARGET_DIR"

if [ "$DRY_RUN" = "yes" ]; then
  exit 0
fi

mkdir -p "$TARGET_ROOT"
rm -rf "$TARGET_DIR"
cp -a "$SOURCE_DIR" "$TARGET_ROOT/"

echo "installed=$TARGET_DIR"
echo 'activate=$vim4-hardware-control'
