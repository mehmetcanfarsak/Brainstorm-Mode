#!/usr/bin/env python3
"""
OpenCode `tool.execute.before` adapter — hard-blocks file-editing tools while
brainstorm mode is active.

Thin shim contract (see ../plugin/brainstorm-mode.ts):
  stdin  : {"session_id": ..., "cwd": ..., "tool_name": ...}
  stdout : a deny-reason string when the call must be blocked; empty otherwise.
           The plugin throws Error(stdout) to block, so any non-empty stdout
           means "deny".
Exit 0 in all cases (fail open on errors — never break the user's session).
"""
import json
import os
import sys

_CORE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "core"))
sys.path.insert(0, _CORE)

from brainstorm_state import append_drift_log, is_post_compact, read_lock

# OpenCode's file-editing tools are lowercase. `edit` rewrites existing files and
# `patch` applies diffs — both are blocked. `write` (new files), `bash`, and `read`
# stay allowed, mirroring the claude-code policy: block edits, permit note-taking
# and exploration.
BLOCKED_TOOLS = frozenset({"edit", "patch"})

_DENY_TEMPLATE = (
    'Brainstorm mode is active (topic: "{topic}"). '
    "Editing existing files is blocked. "
    "Present this as an idea or design note instead, "
    "or use the write tool to save it as a new notes file. "
    "The user can exit with /brainstorm-done."
)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception:
        return

    session_id = data.get("session_id", "").strip()
    cwd = data.get("cwd", os.getcwd())
    tool_name = data.get("tool_name", "") or data.get("tool", "")

    if not session_id or tool_name not in BLOCKED_TOOLS:
        return

    try:
        lock = read_lock(cwd, session_id)
        if not lock:
            return

        topic = lock["topic"]

        append_drift_log(
            cwd,
            session_id,
            topic,
            tool_name,
            lock["created_at"],
            is_post_compact(cwd, session_id),
        )

        print(_DENY_TEMPLATE.format(topic=topic))
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
