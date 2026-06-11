#!/usr/bin/env python3
"""
Deactivate brainstorm mode for the current session.
Called by /brainstorm-done AFTER the convergence summary is produced.

Before unlocking, the session is archived to
<project>/.claude/brainstorm/sessions/<stamp>-<slug>.md with its metadata and
drift events. A convergence handoff piped on stdin (heredoc) is embedded too.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brainstorm_state import archive_session, delete_lock, read_lock


def _read_stdin_handoff():
    """Read a handoff passed on stdin; empty string if none/interactive."""
    try:
        if sys.stdin.isatty():
            return ""
        return sys.stdin.read()
    except Exception:
        return ""


def main(env=None, handoff=None):
    """Returns 0 on success, 1 on error. Accepts optional env/handoff for testability."""
    env = os.environ if env is None else env

    cwd = env.get("BRAINSTORM_CWD") or env.get("CLAUDE_CWD") or os.getcwd()
    session_id = (env.get("BRAINSTORM_SESSION_ID") or env.get("CLAUDE_SESSION_ID", "")).strip()

    if not session_id:
        print("Brainstorm mode was not active (no session ID available).")
        return 0

    if handoff is None:
        handoff = _read_stdin_handoff()

    try:
        lock = read_lock(cwd, session_id)
        if lock:
            archive_path = archive_session(cwd, session_id, handoff)
            delete_lock(cwd, session_id)
            print(f"Brainstorm mode deactivated. Topic was: {lock['topic']}")
            print("File-editing tools (Edit, MultiEdit, NotebookEdit) are now unblocked.")
            if archive_path:
                print(f"Session archived to {archive_path}")
        else:
            print("Brainstorm mode was not active.")
    except Exception as e:
        print(f"deactivate.py error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
