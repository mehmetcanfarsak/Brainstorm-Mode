#!/usr/bin/env python3
"""
OpenCode `experimental.session.compacting` adapter — re-anchors brainstorm mode
across context compaction.

When OpenCode compacts a session it keeps the same session id, so the on-disk
lock still matches. This sets the compaction flag (so post-compaction drift is
distinguishable in the drift log) and returns a one-line anchor that the plugin
pushes into the retained compaction context.

Thin shim contract (see ../plugin/brainstorm-mode.ts):
  stdin  : {"session_id": ..., "cwd": ..., "source": "compact"}
  stdout : a one-line anchor when brainstorm mode is active; empty otherwise.
Exit 0 in all cases (fail open).

Note: OpenCode keeps a stable session id across `continue`/share, so there is no
"resume creates a new session" branch like the claude-code adapter has.
"""
import json
import os
import sys

_CORE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "core"))
sys.path.insert(0, _CORE)

from brainstorm_state import read_lock, set_compact_flag


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception:
        return

    session_id = data.get("session_id", "").strip()
    cwd = data.get("cwd", os.getcwd())
    source = data.get("source", "")

    if not session_id:
        return

    try:
        if source == "compact":
            lock = read_lock(cwd, session_id)
            if lock:
                set_compact_flag(cwd, session_id)
                print(f"Brainstorm mode is still active — topic: {lock['topic']}.")
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
