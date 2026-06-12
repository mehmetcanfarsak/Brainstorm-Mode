#!/usr/bin/env bash
# Install brainstorm-mode into a Claude Code project or globally.
#
# Usage:
#   ./setup.sh --project /path/to/your/project   # project-level install
#   ./setup.sh --global                           # user-level install (~/.claude)
#   ./setup.sh --uninstall --project <path>       # remove from a project
#   ./setup.sh --uninstall --global               # remove from user config

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS_DIR="$PLUGIN_ROOT/agents/claude-code/hooks_scripts"
CMD_SRC="$PLUGIN_ROOT/agents/claude-code/commands"

usage() {
  cat >&2 <<EOF
Usage:
  $0 --project <path>           Install into a specific project
  $0 --global                   Install into ~/.claude (all sessions)
  $0 --uninstall --project <path>
  $0 --uninstall --global
EOF
  exit 1
}

require_jq() {
  if ! command -v jq &>/dev/null; then
    echo "Error: jq is required. Install it (e.g. 'brew install jq' or 'apt install jq') and retry." >&2
    exit 1
  fi
}

# ── Argument parsing ──────────────────────────────────────────────────────────
MODE=""
TARGET_DIR=""
UNINSTALL=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)
      [[ -z "${2:-}" ]] && { echo "Error: --project requires a path." >&2; usage; }
      MODE="project"
      TARGET_DIR="$2"
      shift 2
      ;;
    --global)
      MODE="global"
      TARGET_DIR="$HOME/.claude"
      shift
      ;;
    --uninstall)
      UNINSTALL=true
      shift
      ;;
    *)
      usage
      ;;
  esac
done

[[ -z "$MODE" ]] && usage

# ── Resolve paths ─────────────────────────────────────────────────────────────
if [[ "$MODE" == "project" ]]; then
  [[ -d "$TARGET_DIR" ]] || { echo "Error: project directory '$TARGET_DIR' does not exist." >&2; exit 1; }
  CLAUDE_DIR="$TARGET_DIR/.claude"
else
  CLAUDE_DIR="$TARGET_DIR"
fi

SETTINGS="$CLAUDE_DIR/settings.json"
CMD_DST="$CLAUDE_DIR/commands"

# ── Uninstall ─────────────────────────────────────────────────────────────────
if $UNINSTALL; then
  echo "Removing brainstorm-mode commands ..."
  rm -f "$CMD_DST/brainstorm.md" "$CMD_DST/brainstorm-actionable.md" "$CMD_DST/brainstorm-done.md"

  if [[ -f "$SETTINGS" ]] && command -v jq &>/dev/null; then
    echo "Removing brainstorm-mode hooks from $SETTINGS ..."
    TMP="$(mktemp)"
    jq '
      .hooks.UserPromptSubmit = [.hooks.UserPromptSubmit[]? | select(.hooks[]?.command | contains("brainstorm") | not)] |
      .hooks.PreToolUse       = [.hooks.PreToolUse[]?       | select(.hooks[]?.command | contains("brainstorm") | not)] |
      .hooks.SessionStart     = [.hooks.SessionStart[]?     | select(.hooks[]?.command | contains("brainstorm") | not)]
    ' "$SETTINGS" > "$TMP" && mv "$TMP" "$SETTINGS"
  fi

  echo "Done. brainstorm-mode has been removed."
  exit 0
fi

# ── Install ───────────────────────────────────────────────────────────────────
require_jq
mkdir -p "$CMD_DST"

echo "Installing commands to $CMD_DST ..."
for f in brainstorm.md brainstorm-actionable.md brainstorm-done.md; do
  sed "s|\${CLAUDE_PLUGIN_ROOT}|$PLUGIN_ROOT|g" "$CMD_SRC/$f" > "$CMD_DST/$f"
done

echo "Merging hooks into $SETTINGS ..."
[[ -f "$SETTINGS" ]] || echo '{}' > "$SETTINGS"

# Idempotent: strip any existing brainstorm-mode hooks, then re-add.
TMP="$(mktemp)"
jq --arg up  "python3 $SCRIPTS_DIR/on_user_prompt.py" \
   --arg pre "python3 $SCRIPTS_DIR/on_pre_tool_use.py" \
   --arg ss  "python3 $SCRIPTS_DIR/on_session_start.py" '
  # Remove existing brainstorm entries first so this is safe to run repeatedly.
  (.hooks.UserPromptSubmit // []) |= map(select(.hooks[]?.command | contains("brainstorm") | not)) |
  (.hooks.PreToolUse       // []) |= map(select(.hooks[]?.command | contains("brainstorm") | not)) |
  (.hooks.SessionStart     // []) |= map(select(.hooks[]?.command | contains("brainstorm") | not)) |
  # Add fresh entries.
  .hooks.UserPromptSubmit += [{"hooks": [{"type": "command", "command": $up}]}] |
  .hooks.PreToolUse       += [{"matcher": "Edit|MultiEdit|NotebookEdit", "hooks": [{"type": "command", "command": $pre}]}] |
  .hooks.SessionStart     += [{"hooks": [{"type": "command", "command": $ss}]}]
' "$SETTINGS" > "$TMP" && mv "$TMP" "$SETTINGS"

echo ""
echo "brainstorm-mode installed successfully."
echo "  Commands : $CMD_DST/brainstorm.md, brainstorm-actionable.md, brainstorm-done.md"
echo "  Hooks    : $SETTINGS"
echo ""
echo "Open a new Claude Code session in $TARGET_DIR to start using /brainstorm."
