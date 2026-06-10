#!/usr/bin/env python3
"""
SessionStart hook — best-effort re-anchor and resume notice.

compact  → same session_id, lock still matches → set compaction flag + inject one-liner
resume   → new session_id, old lock won't match → scan for recently active lock and inform user

All failures are silent; exit 0 always.
"""
import json
import os
import sys

_CORE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "core"))
sys.path.insert(0, _CORE)

from brainstorm_state import find_recent_lock, read_lock, set_compact_flag


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

        elif source == "resume":
            # New session_id: any lock for this session_id won't exist.
            # Scan for a lock from the previous session so we can inform the user.
            old_lock = find_recent_lock(cwd)
            if old_lock and old_lock.get("session_id") != session_id:
                topic = old_lock.get("topic", "")
                print(
                    f"A brainstorm session on '{topic}' was active before resume. "
                    f"Brainstorm mode is NOT currently active; "
                    f"run /brainstorm {topic} to re-enter."
                )
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
