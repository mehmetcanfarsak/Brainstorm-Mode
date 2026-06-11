#!/usr/bin/env python3
"""
Deactivate brainstorm mode for the current session.
Called by /brainstorm-done AFTER the convergence summary is produced.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brainstorm_state import delete_lock, read_lock


def main(env=None):
    """Returns 0 on success, 1 on error. Accepts optional env for testability."""
    env = os.environ if env is None else env

    cwd = env.get("BRAINSTORM_CWD") or env.get("CLAUDE_CWD") or os.getcwd()
    session_id = (env.get("BRAINSTORM_SESSION_ID") or env.get("CLAUDE_SESSION_ID", "")).strip()

    if not session_id:
        print("Brainstorm mode was not active (no session ID available).")
        return 0

    try:
        lock = read_lock(cwd, session_id)
        if lock:
            delete_lock(cwd, session_id)
            print(f"Brainstorm mode deactivated. Topic was: {lock['topic']}")
            print("File-editing tools (Edit, MultiEdit, NotebookEdit) are now unblocked.")
        else:
            print("Brainstorm mode was not active.")
    except Exception as e:
        print(f"deactivate.py error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
