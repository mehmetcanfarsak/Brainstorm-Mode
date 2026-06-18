#!/usr/bin/env python3
"""
Activate brainstorm mode for the current session.
Called by the /brainstorm and /brainstorm-actionable commands:
    python3 activate.py [--mode divergent|actionable] <topic...>

Session ID is read from BRAINSTORM_SESSION_ID (agent-neutral) or, for backward
compatibility, CLAUDE_SESSION_ID. If unavailable, a _pending lock is written and
claimed by the next per-prompt hook invocation.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from brainstorm_state import (
    DEFAULT_MODE,
    MODES,
    cleanup_old_locks,
    load_brainstorm_config,
    read_lock,
    update_venues,
    write_lock,
    write_pending_lock,
)

_USAGE = (
    f"Usage: activate.py [--mode {'|'.join(MODES)}] [--venues <list>] <topic>\n"
    "       activate.py --add-venues <list>   (amend the active session's venues)"
)


def main(argv=None, env=None):
    """Returns 0 on success, 1 on error. Accepts optional argv/env for testability."""
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env

    args = list(argv[1:])
    mode = DEFAULT_MODE
    venues = None
    add_venues = None
    while args and args[0] in ("--mode", "--venues", "--add-venues"):
        flag = args.pop(0)
        if not args:
            print(_USAGE, file=sys.stderr)
            return 1
        value = args.pop(0)
        if flag == "--mode":
            if value not in MODES:
                print(_USAGE, file=sys.stderr)
                return 1
            mode = value
        elif flag == "--venues":
            venues = value
        else:
            add_venues = value

    cwd = env.get("BRAINSTORM_CWD") or env.get("CLAUDE_CWD") or os.getcwd()
    session_id = (env.get("BRAINSTORM_SESSION_ID") or env.get("CLAUDE_SESSION_ID", "")).strip()

    # Mid-session amendment: broaden the allowed venues of the active lock. No topic needed.
    if add_venues is not None:
        if not session_id:
            print("activate.py error: --add-venues needs an active session id.", file=sys.stderr)
            return 1
        try:
            merged = update_venues(cwd, session_id, add_venues)
        except Exception as e:
            print(f"activate.py error: {e}", file=sys.stderr)
            return 1
        if merged is None:
            print("No active brainstorm session to amend.")
        else:
            print(f"Allowed venues updated: {merged}")
        return 0

    if not args:
        print(_USAGE, file=sys.stderr)
        return 1

    topic = " ".join(args)
    # Academic sessions with no explicit --venues fall back to the configured
    # venue preset (.brainstorm / ~/.config/brainstorm/config). Pass --venues ""
    # to opt out explicitly.
    if venues is None and mode == "academic":
        venues = load_brainstorm_config(cwd, env).get("venues")
    label = "Brainstorm mode" if mode == DEFAULT_MODE else f"Brainstorm mode ({mode})"

    try:
        cleanup_old_locks(cwd)
        if session_id:
            existing = read_lock(cwd, session_id)
            write_lock(cwd, session_id, topic, mode, venues)
            if existing:
                print(f"{label} topic updated to: {topic}")
            else:
                print(f"{label} activated. Topic: {topic}")
        else:
            write_pending_lock(cwd, topic, mode, venues)
            print(f"{label} activating. Topic: {topic}")
            print("(Session lock will be claimed on the next user prompt.)")
        if venues:
            print(f"Primary references restricted to: {venues}")
    except Exception as e:
        print(f"activate.py error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
