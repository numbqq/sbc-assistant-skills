#!/usr/bin/env bash
set -euo pipefail

TOOL="codex"
SKILL="all"
DRY_RUN="no"
LIST_TOOLS="no"

usage() {
  cat <<USAGE
Usage:
  $0 [--tool TOOL] [--skill NAME|all] [--dry-run]
  $0 --tool all [--skill NAME|all]
  $0 --list-tools
  $0 --help

Options:
  --tool TOOL       Install to one supported agent/tool. Default: codex.
  --tool all        Install to every supported agent/tool.
  --skill NAME      Install one skill directory name. Default: all.
  --dry-run         Print planned install paths without copying files.
  --list-tools      Show supported agent/tool targets.
  --help            Show this help.

Environment overrides:
  CODEX_HOME          Codex home directory. Default: \$HOME/.codex
  CLAUDE_AGENTS_DIR   Claude Code agents directory. Default: \$HOME/.claude/agents
  HERMES_SKILLS_DIR   Hermes skills directory. Default: \$HOME/.hermes/skills
  OPENCLAW_AGENTS_DIR OpenClaw agents directory. Default: \$HOME/.openclaw/agency-agents
USAGE
}

supported_tools() {
  printf '%s\n' codex claude-code hermes openclaw
}

target_root_for_tool() {
  case "$1" in
    codex)
      printf '%s\n' "${CODEX_HOME:-$HOME/.codex}/skills"
      ;;
    hermes)
      printf '%s\n' "${HERMES_SKILLS_DIR:-$HOME/.hermes/skills}"
      ;;
    claude-code)
      printf '%s\n' "${CLAUDE_AGENTS_DIR:-$HOME/.claude/agents}"
      ;;
    openclaw)
      printf '%s\n' "${OPENCLAW_AGENTS_DIR:-$HOME/.openclaw/agency-agents}"
      ;;
    *)
      return 1
      ;;
  esac
}

is_supported_tool() {
  local candidate="$1"
  local tool
  for tool in $(supported_tools); do
    if [ "$candidate" = "$tool" ]; then
      return 0
    fi
  done
  return 1
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --tool)
      TOOL="${2:?tool name required}"
      shift 2
      ;;
    --skill)
      SKILL="${2:?skill name required}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN="yes"
      shift
      ;;
    --list-tools)
      LIST_TOOLS="yes"
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

if [ "$LIST_TOOLS" = "yes" ]; then
  supported_tools
  exit 0
fi

if [ "$TOOL" != "all" ] && ! is_supported_tool "$TOOL"; then
  echo "unsupported tool: $TOOL" >&2
  echo "supported tools:" >&2
  supported_tools >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_ROOT="$REPO_ROOT/codex"
INTEGRATIONS_ROOT="$REPO_ROOT/integrations"

test -d "$SOURCE_ROOT" || { echo "missing source root: $SOURCE_ROOT" >&2; exit 1; }

collect_skill_dirs() {
  local dir
  if [ "$SKILL" = "all" ]; then
    for dir in "$SOURCE_ROOT"/*; do
      [ -d "$dir" ] || continue
      [ -f "$dir/SKILL.md" ] || continue
      printf '%s\n' "$dir"
    done
  else
    dir="$SOURCE_ROOT/$SKILL"
    [ -d "$dir" ] || { echo "missing skill directory: $dir" >&2; return 1; }
    [ -f "$dir/SKILL.md" ] || { echo "missing skill file: $dir/SKILL.md" >&2; return 1; }
    printf '%s\n' "$dir"
  fi
}

install_skill_for_tool() {
  local tool="$1"
  local source_dir="$2"
  local target_root
  local skill_dir_name
  local agent_name
  local target_dir
  local converted_source

  target_root="$(target_root_for_tool "$tool")"
  skill_dir_name="$(basename "$source_dir")"
  agent_name="$(awk '/^name:[[:space:]]*/ { sub(/^name:[[:space:]]*/, ""); print; exit }' "$source_dir/SKILL.md")"
  agent_name="${agent_name%\"}"
  agent_name="${agent_name#\"}"
  agent_name="${agent_name%\'}"
  agent_name="${agent_name#\'}"
  [ -n "$agent_name" ] || agent_name="${skill_dir_name%-skills}"

  if [ "$tool" = "claude-code" ]; then
    target_dir="$target_root/$agent_name.md"
  elif [ "$tool" = "openclaw" ]; then
    target_dir="$target_root/$agent_name"
  else
    target_dir="$target_root/$skill_dir_name"
  fi

  echo "tool=$tool"
  echo "source=$source_dir"
  echo "target=$target_dir"

  if [ "$DRY_RUN" = "yes" ]; then
    return 0
  fi

  mkdir -p "$target_root"
  if [ "$tool" = "claude-code" ]; then
    converted_source="$INTEGRATIONS_ROOT/claude-code/agents/$agent_name.md"
    rm -f "$target_dir"
    if [ -f "$converted_source" ]; then
      cp "$converted_source" "$target_dir"
    else
      cp "$source_dir/SKILL.md" "$target_dir"
    fi
  elif [ "$tool" = "openclaw" ]; then
    converted_source="$INTEGRATIONS_ROOT/openclaw/agents/$agent_name"
    if [ ! -d "$converted_source" ]; then
      echo "missing converted OpenClaw agent: $converted_source" >&2
      echo "run: $REPO_ROOT/scripts/convert.sh --tool openclaw --skill $skill_dir_name" >&2
      exit 1
    fi

    rm -rf "$target_dir"
    cp -a "$converted_source" "$target_dir"
  else
    rm -rf "$target_dir"
    cp -a "$source_dir" "$target_root/"
  fi

  echo "installed=$target_dir"
}

SKILL_DIRS="$(collect_skill_dirs)"
if [ -z "$SKILL_DIRS" ]; then
  echo "no installable skills found under: $SOURCE_ROOT" >&2
  exit 1
fi

if [ "$TOOL" = "all" ]; then
  TOOLS="$(supported_tools)"
else
  TOOLS="$TOOL"
fi

for tool in $TOOLS; do
  while IFS= read -r source_dir; do
    [ -n "$source_dir" ] || continue
    install_skill_for_tool "$tool" "$source_dir"
  done <<EOF
$SKILL_DIRS
EOF
done

echo "activation:"
for tool in $TOOLS; do
  case "$tool" in
    codex)
      echo 'codex=$vim4-hardware-control'
      ;;
    claude-code)
      echo 'claude-code=restart Claude Code, then use the vim4-hardware-control subagent'
      ;;
    hermes)
      echo 'hermes=restart Hermes, then use the vim4-hardware-control skill'
      ;;
    openclaw)
      echo 'openclaw=restart OpenClaw gateway, then use the vim4-hardware-control agent'
      ;;
  esac
done
