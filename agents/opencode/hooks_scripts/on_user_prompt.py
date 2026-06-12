#!/usr/bin/env python3
"""
OpenCode `chat.message` adapter — re-injects the brainstorm-mode constraint on
every user message. The plugin appends stdout to the message parts, so the
reminder is re-established every turn (this is what survives long sessions).

Thin shim contract (see ../plugin/brainstorm-mode.ts):
  stdin  : {"session_id": ..., "cwd": ...}
  stdout : the reminder string when brainstorm mode is active; empty otherwise.
Exit 0 in all cases (fail open — any error means no injection).
"""
import json
import os
import sys

_CORE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "core"))
sys.path.insert(0, _CORE)

from brainstorm_state import (
    claim_pending_lock,
    cleanup_old_locks,
    count_session_drift,
    get_expiry_notice,
    get_reminder,
    pop_expiry_notice,
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
            # Claim a pending lock written by activate.py when the session id was
            # not yet available at command-invocation time.
            topic = claim_pending_lock(cwd, session_id)
            if topic is not None:
                lock = read_lock(cwd, session_id)

        if lock:
            print(get_reminder(
                lock["topic"],
                count_session_drift(cwd, session_id),
                lock.get("mode", "divergent"),
            ))
        else:
            # No active lock — if one just hit its TTL, say so loudly.
            expired_topic = pop_expiry_notice(cwd, session_id)
            if expired_topic is not None:
                print(get_expiry_notice(expired_topic))
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()
