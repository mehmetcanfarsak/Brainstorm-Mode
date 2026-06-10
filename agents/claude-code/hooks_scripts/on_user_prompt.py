#!/usr/bin/env python3
"""
UserPromptSubmit hook — re-injects the brainstorm-mode constraint on every prompt.
Stdout becomes injected context prepended to the user's message.
All error paths exit 0 with no output (fail open).
"""
import json
import os
import sys

_CORE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "core"))
sys.path.insert(0, _CORE)

from brainstorm_state import (
    cleanup_old_locks,
    claim_pending_lock,
    get_reminder,
    read_lock,
)


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception:
        return

    session_id = data.get("session_id", "").strip()
    cwd = data.get("cwd", os.getcwd())

    if not session_id:
        return

    try:
        cleanup_old_locks(cwd)

        lock = read_lock(cwd, session_id)
        if lock is None:
            # Try to claim a pending lock written by activate.py when session_id
            # was not yet available at command invocation time.
            topic = claim_pending_lock(cwd, session_id)
            if topic is not None:
                lock = read_lock(cwd, session_id)

        if lock:
            print(get_reminder(lock["topic"]))
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
