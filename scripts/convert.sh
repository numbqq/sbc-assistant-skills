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
  $0 --codex|--claude-code|--gemini-cli|--hermes|--openclaw [--skill NAME|all]
  $0 --list-tools
  $0 --help

Options:
  --tool TOOL       Convert to one supported integration format.
  --tool all        Convert to every supported integration format. Default: all.
  --codex           No conversion needed; install with install.sh.
  --claude-code     No conversion needed; install with install.sh.
  --gemini-cli      Convert to Gemini CLI extensions.
  --hermes          No conversion needed; install with install.sh.
  --openclaw        Convert to OpenClaw agent workspaces.
  --skill NAME      Convert one skill directory name. Default: all.
  --list-tools      Show supported targets.
  --help            Show this help.
USAGE
}

conversion_tools() {
  printf '%s\n' gemini-cli openclaw
}

native_tools() {
  printf '%s\n' codex claude-code hermes
}

supported_tools() {
  native_tools
  conversion_tools
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

json_escape() {
  sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'
}

display_name_for_skill() {
  local source_dir="$1"
  local agent_name="$2"
  local value

  value="$(awk -F'"' '/display_name:/ { print $2; exit }' "$source_dir/agents/openai.yaml" 2>/dev/null || true)"
  [ -n "$value" ] || value="$agent_name"
  printf '%s\n' "$value"
}

skill_name_for_dir() {
  local source_dir="$1"
  local skill_dir_name
  local agent_name

  skill_dir_name="$(basename "$source_dir")"
  agent_name="$(frontmatter_value name "$source_dir/SKILL.md")"
  [ -n "$agent_name" ] || agent_name="${skill_dir_name%-skills}"
  printf '%s\n' "$agent_name"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --tool)
      TOOL="${2:?tool name required}"
      shift 2
      ;;
    --codex)
      TOOL="codex"
      shift
      ;;
    --claude-code)
      TOOL="claude-code"
      shift
      ;;
    --gemini-cli)
      TOOL="gemini-cli"
      shift
      ;;
    --hermes)
      TOOL="hermes"
      shift
      ;;
    --openclaw)
      TOOL="openclaw"
      shift
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
  echo "unsupported target: $TOOL" >&2
  echo "supported targets:" >&2
  supported_tools >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_ROOT="$REPO_ROOT/skills"
INTEGRATIONS_ROOT="$REPO_ROOT/integrations"

test -d "$SOURCE_ROOT" || { echo "missing source root: $SOURCE_ROOT" >&2; exit 1; }

collect_skill_dirs() {
  local dir
  local skill_file
  local found="no"

  if [ "$SKILL" = "all" ]; then
    while IFS= read -r skill_file; do
      [ -n "$skill_file" ] || continue
      dirname "$skill_file"
    done <<EOF
$(find "$SOURCE_ROOT" -type f -name SKILL.md | sort)
EOF
    return 0
  fi

  if [ -f "$SOURCE_ROOT/$SKILL/SKILL.md" ]; then
    printf '%s\n' "$SOURCE_ROOT/$SKILL"
    return 0
  fi

  while IFS= read -r skill_file; do
    [ -n "$skill_file" ] || continue
    dir="$(dirname "$skill_file")"
    if [ "$(basename "$dir")" = "$SKILL" ] || [ "$(frontmatter_value name "$skill_file")" = "$SKILL" ]; then
      printf '%s\n' "$dir"
      found="yes"
    fi
  done <<EOF
$(find "$SOURCE_ROOT" -type f -name SKILL.md | sort)
EOF

  if [ "$found" = "no" ]; then
    echo "missing skill: $SKILL" >&2
    return 1
  fi
}

convert_gemini_cli() {
  local source_dir="$1"
  local agent_name
  local description
  local escaped_description
  local target_dir

  agent_name="$(skill_name_for_dir "$source_dir")"
  description="$(frontmatter_value description "$source_dir/SKILL.md")"
  escaped_description="$(printf '%s' "$description" | json_escape)"
  target_dir="$INTEGRATIONS_ROOT/gemini-cli/extensions/$agent_name"

  rm -rf "$target_dir"
  mkdir -p "$target_dir/skill"

  cat > "$target_dir/gemini-extension.json" <<EOF
{
  "name": "$agent_name",
  "version": "1.0.0",
  "description": "$escaped_description",
  "contextFileName": "GEMINI.md"
}
EOF

  cat > "$target_dir/GEMINI.md" <<EOF
# $agent_name

This Gemini CLI extension was generated from the $agent_name skill.

Use the instructions below as the assistant's operating rules. Bundled
references and helper scripts are copied under ./skill/ for local lookup.

EOF
  skill_body "$source_dir/SKILL.md" >> "$target_dir/GEMINI.md"
  cp -a "$source_dir/." "$target_dir/skill/"

  echo "converted=gemini-cli:$target_dir"
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

report_native_tool() {
  local tool="$1"
  local source_dir="$2"
  local agent_name

  agent_name="$(skill_name_for_dir "$source_dir")"
  echo "native=$tool:$agent_name"
  echo "run: $REPO_ROOT/scripts/install.sh --tool $tool --skill $agent_name"
}

reset_selected_integrations() {
  local tool

  if [ "$TOOL" = "all" ]; then
    rm -rf "$INTEGRATIONS_ROOT/claude-code"
  fi

  for tool in $TOOLS; do
    case "$tool" in
      gemini-cli)
        rm -rf "$INTEGRATIONS_ROOT/gemini-cli"
        ;;
      openclaw)
        rm -rf "$INTEGRATIONS_ROOT/openclaw"
        ;;
    esac
  done
}

SKILL_DIRS="$(collect_skill_dirs)"
if [ -z "$SKILL_DIRS" ]; then
  echo "no installable skills found under: $SOURCE_ROOT" >&2
  exit 1
fi

if [ "$TOOL" = "all" ]; then
  TOOLS="$(conversion_tools)"
else
  TOOLS="$TOOL"
fi

reset_selected_integrations

for tool in $TOOLS; do
  while IFS= read -r source_dir; do
    [ -n "$source_dir" ] || continue
    case "$tool" in
      gemini-cli)
        convert_gemini_cli "$source_dir"
        ;;
      openclaw)
        convert_openclaw "$source_dir"
        ;;
      codex|claude-code|hermes)
        report_native_tool "$tool" "$source_dir"
        ;;
    esac
  done <<EOF
$SKILL_DIRS
EOF
done
