#!/usr/bin/env bash
set -euo pipefail

TOOL="all"
SKILL="all"
LIST_TOOLS="no"

usage() {
  cat <<USAGE
Usage:
  $0 [--tool TOOL] [--skill NAME|all]
  $0 --tool all [--skill NAME|all]
  $0 --list-tools
  $0 --help

Options:
  --tool TOOL       Convert to one supported integration format.
  --tool all        Convert to every supported integration format. Default: all.
  --skill NAME      Convert one skill directory name. Default: all.
  --list-tools      Show supported conversion targets.
  --help            Show this help.
USAGE
}

supported_tools() {
  printf '%s\n' claude-code openclaw
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

frontmatter_value() {
  local key="$1"
  local file="$2"
  local value

  value="$(awk -v key="$key" '
    $0 == "---" && seen == 0 { seen = 1; next }
    $0 == "---" && seen == 1 { exit }
    seen == 1 && index($0, key ":") == 1 {
      sub("^[^:]+:[[:space:]]*", "")
      print
      exit
    }
  ' "$file")"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s\n' "$value"
}

skill_body() {
  awk '
    NR == 1 && $0 == "---" { frontmatter = 1; next }
    frontmatter && $0 == "---" { frontmatter = 0; next }
    !frontmatter { print }
  ' "$1"
}

display_name_for_skill() {
  local source_dir="$1"
  local agent_name="$2"
  local value

  value="$(awk -F'"' '/display_name:/ { print $2; exit }' "$source_dir/agents/openai.yaml" 2>/dev/null || true)"
  [ -n "$value" ] || value="$agent_name"
  printf '%s\n' "$value"
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
  echo "unsupported conversion target: $TOOL" >&2
  echo "supported conversion targets:" >&2
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

convert_claude_code() {
  local source_dir="$1"
  local agent_name
  local target_dir
  local target_file

  agent_name="$(frontmatter_value name "$source_dir/SKILL.md")"
  [ -n "$agent_name" ] || agent_name="$(basename "$source_dir" | sed 's/-skills$//')"
  target_dir="$INTEGRATIONS_ROOT/claude-code/agents"
  target_file="$target_dir/$agent_name.md"

  mkdir -p "$target_dir"
  cp "$source_dir/SKILL.md" "$target_file"
  echo "converted=claude-code:$target_file"
}

convert_openclaw() {
  local source_dir="$1"
  local agent_name
  local description
  local display_name
  local target_dir

  agent_name="$(frontmatter_value name "$source_dir/SKILL.md")"
  [ -n "$agent_name" ] || agent_name="$(basename "$source_dir" | sed 's/-skills$//')"
  description="$(frontmatter_value description "$source_dir/SKILL.md")"
  display_name="$(display_name_for_skill "$source_dir" "$agent_name")"
  target_dir="$INTEGRATIONS_ROOT/openclaw/agents/$agent_name"

  rm -rf "$target_dir"
  mkdir -p "$target_dir/skill"

  cat > "$target_dir/SOUL.md" <<EOF
# $display_name

You are $display_name, a focused specialist agent.

Core behavior:
- Stay within the scope defined in AGENTS.md.
- Prefer precise, minimal, verifiable steps.
- Call out hardware or system safety risks before suggesting state-changing commands.
- Ask for missing board, wiring, bus, pin, or permission details when guessing would be unsafe.
EOF

  cat > "$target_dir/IDENTITY.md" <<EOF
name: $display_name
theme: $description
EOF

  cat > "$target_dir/AGENTS.md" <<EOF
# $display_name

This OpenClaw workspace was generated from the $agent_name skill.

Use the instructions below as the agent's operating rules. Bundled references
and helper scripts are copied under ./skill/ for local lookup.

EOF
  skill_body "$source_dir/SKILL.md" >> "$target_dir/AGENTS.md"
  cp -a "$source_dir/." "$target_dir/skill/"

  echo "converted=openclaw:$target_dir"
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

rm -rf "$INTEGRATIONS_ROOT"

for tool in $TOOLS; do
  while IFS= read -r source_dir; do
    [ -n "$source_dir" ] || continue
    case "$tool" in
      claude-code)
        convert_claude_code "$source_dir"
        ;;
      openclaw)
        convert_openclaw "$source_dir"
        ;;
    esac
  done <<EOF
$SKILL_DIRS
EOF
done
