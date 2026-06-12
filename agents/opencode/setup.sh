#!/usr/bin/env bash
# Install brainstorm-mode into an OpenCode project or globally.
#
# Unlike the claude-code installer, OpenCode auto-loads plugin and command files
# from its config directories, so there is no settings.json to merge and no jq
# dependency — this script just copies files and bakes in absolute paths.
#
# Usage:
#   ./setup.sh --project /path/to/your/project   # → <project>/.opencode/
#   ./setup.sh --global                           # → ~/.config/opencode/
#   ./setup.sh --uninstall --project <path>
#   ./setup.sh --uninstall --global

set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPTS_DIR="$PLUGIN_ROOT/agents/opencode/hooks_scripts"
PLUGIN_SRC="$PLUGIN_ROOT/agents/opencode/plugin/brainstorm-mode.ts"
CMD_SRC="$PLUGIN_ROOT/agents/opencode/commands"

usage() {
  cat >&2 <<EOF
Usage:
  $0 --project <path>           Install into a specific project (.opencode/)
  $0 --global                   Install into ~/.config/opencode (all sessions)
  $0 --uninstall --project <path>
  $0 --uninstall --global
EOF
  exit 1
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

# ── Resolve the OpenCode config directory ─────────────────────────────────────
if [[ "$MODE" == "project" ]]; then
  [[ -d "$TARGET_DIR" ]] || { echo "Error: project directory '$TARGET_DIR' does not exist." >&2; exit 1; }
  OC_DIR="$TARGET_DIR/.opencode"
else
  OC_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
fi

PLUGIN_DST="$OC_DIR/plugins"
CMD_DST="$OC_DIR/commands"

# ── Uninstall ─────────────────────────────────────────────────────────────────
if $UNINSTALL; then
  echo "Removing brainstorm-mode from $OC_DIR ..."
  rm -f "$PLUGIN_DST/brainstorm-mode.ts"
  rm -f "$CMD_DST/brainstorm.md" "$CMD_DST/brainstorm-actionable.md" "$CMD_DST/brainstorm-done.md"
  echo "Done. brainstorm-mode has been removed."
  exit 0
fi

# ── Install ───────────────────────────────────────────────────────────────────
mkdir -p "$PLUGIN_DST" "$CMD_DST"

echo "Installing plugin to $PLUGIN_DST ..."
sed "s|__BRAINSTORM_SCRIPTS_DIR__|$SCRIPTS_DIR|g" "$PLUGIN_SRC" > "$PLUGIN_DST/brainstorm-mode.ts"

echo "Installing commands to $CMD_DST ..."
for f in brainstorm.md brainstorm-actionable.md brainstorm-done.md; do
  sed "s|__BRAINSTORM_ROOT__|$PLUGIN_ROOT|g" "$CMD_SRC/$f" > "$CMD_DST/$f"
done

echo ""
echo "brainstorm-mode installed successfully."
echo "  Plugin   : $PLUGIN_DST/brainstorm-mode.ts"
echo "  Commands : $CMD_DST/brainstorm.md, brainstorm-actionable.md, brainstorm-done.md"
echo ""
echo "Requires python3 on PATH. Open a new OpenCode session to use /brainstorm."
