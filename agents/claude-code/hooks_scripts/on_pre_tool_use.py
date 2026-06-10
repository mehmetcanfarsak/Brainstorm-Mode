#!/usr/bin/env python3
"""
PreToolUse hook — hard-blocks Edit / MultiEdit / NotebookEdit while brainstorm mode is active.

Matched tools: Edit, MultiEdit, NotebookEdit  (Bash and Write are intentionally NOT matched)
Decision JSON is written to stdout; exit 0 in all cases (fail open on errors).
"""
import json
import os
import sys

_CORE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "core"))
sys.path.insert(0, _CORE)

from brainstorm_state import (
    BLOCKED_TOOLS,
    append_drift_log,
    is_post_compact,
    read_lock,
)

_DENY_TEMPLATE = (
    'Brainstorm mode is active (topic: "{topic}"). '
    "Editing existing files is blocked. "
    "Present this as an idea or design note instead, "
    "or use Write to save it as a new notes file. "
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

        decision = {
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "denyReason": _DENY_TEMPLATE.format(topic=topic),
            }
        }
        print(json.dumps(decision))
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
