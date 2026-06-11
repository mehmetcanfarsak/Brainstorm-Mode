#!/usr/bin/env python3
"""
Activate brainstorm mode for the current session.
Called by the /brainstorm command: python3 activate.py <topic...>

Session ID is read from BRAINSTORM_SESSION_ID (agent-neutral) or, for backward
compatibility, CLAUDE_SESSION_ID. If unavailable, a _pending lock is written and
claimed by the next per-prompt hook invocation.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brainstorm_state import (
    cleanup_old_locks,
    read_lock,
    write_lock,
    write_pending_lock,
)


def main(argv=None, env=None):
    """Returns 0 on success, 1 on error. Accepts optional argv/env for testability."""
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env

    if len(argv) < 2:
        print("Usage: activate.py <topic>", file=sys.stderr)
        return 1

    topic = " ".join(argv[1:])
    cwd = env.get("BRAINSTORM_CWD") or env.get("CLAUDE_CWD") or os.getcwd()
    session_id = (env.get("BRAINSTORM_SESSION_ID") or env.get("CLAUDE_SESSION_ID", "")).strip()

    try:
        cleanup_old_locks(cwd)
        if session_id:
            existing = read_lock(cwd, session_id)
            write_lock(cwd, session_id, topic)
            if existing:
                print(f"Brainstorm mode topic updated to: {topic}")
            else:
                print(f"Brainstorm mode activated. Topic: {topic}")
        else:
            write_pending_lock(cwd, topic)
            print(f"Brainstorm mode activating. Topic: {topic}")
            print("(Session lock will be claimed on the next user prompt.)")
    except Exception as e:
        print(f"activate.py error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
