# Contributing to brainstorm-mode

Thank you for your interest in contributing. This document covers bug reports, feature requests, and the most common contribution path: adding support for a new coding agent.

---

## Table of contents

- [Reporting bugs](#reporting-bugs)
- [Requesting features](#requesting-features)
- [Development setup](#development-setup)
- [Adding a new agent integration](#adding-a-new-agent-integration)
- [Pull request process](#pull-request-process)
- [Code standards](#code-standards)

---

## Reporting bugs

Use the [Bug Report](https://github.com/mehmetcanfarsak/Brainstorm-Mode/issues/new?template=bug_report.yml) issue template. Include:

- Which agent integration you are using (claude-code, codex, opencode)
- The exact command or hook that failed
- What you expected vs. what happened
- Your Python version (`python3 --version`)
- Sanitized hook input JSON if relevant (remove any sensitive content from file paths or session IDs)

---

## Requesting features

Use the [Feature Request](https://github.com/mehmetcanfarsak/Brainstorm-Mode/issues/new?template=feature_request.yml) issue template. Before opening one, check whether it conflicts with the explicit non-goals in the spec:

- No daemon, no background process, no network calls
- No bash-command parsing/classification
- No config file (constants live in `brainstorm_state.py`)
- No attempt to make mode survive `--resume`

---

## Development setup

```bash
git clone https://github.com/mehmetcanfarsak/Brainstorm-Mode
cd Brainstorm-Mode

# Run the tests (no install needed — stdlib only)
make test

# Check coverage
make coverage
```

Requirements: Python 3.8+, `jq` (only needed for `setup.sh`, not for tests).

### Manually testing a hook script

Hook scripts read JSON from stdin, so you can exercise them directly with the
fixtures in `tests/fixtures/` (inject a `cwd` pointing at a scratch dir with a
lock file). For example:

```bash
echo '{"session_id":"s1","cwd":"/tmp/demo","tool_name":"Edit"}' \
  | python3 agents/claude-code/hooks_scripts/on_pre_tool_use.py
```

With an active lock under `/tmp/demo/.claude/brainstorm/locks/s1.json`, this
prints a deny decision; without one, it prints nothing (fail open).

---

## Adding a new agent integration

This is the primary contribution path. The codebase is structured so that `core/` is agent-agnostic and all agent-specific code lives in `agents/<agent-name>/`.

### Step 1 — Create the directory structure

```
agents/<agent-name>/
├── commands/
│   ├── brainstorm.md
│   └── brainstorm-done.md
├── hooks/
│   └── hooks.json
├── hooks_scripts/
│   ├── on_user_prompt.py
│   ├── on_pre_tool_use.py
│   └── on_session_start.py
└── setup.sh
```

### Step 2 — Research the agent's hook system

Before writing any code, answer these questions and document your findings in a comment at the top of each hook script:

| Question | Claude Code answer | Your agent |
|---|---|---|
| What are the hook event names? | `UserPromptSubmit`, `PreToolUse`, `SessionStart` | ? |
| How is hook input delivered? | JSON on stdin | ? |
| What fields does the input include? | `session_id`, `cwd`, `tool_name`, `source`, … | ? |
| How do you inject context (UserPromptSubmit)? | Print to stdout, exit 0 | ? |
| How do you deny a tool call (PreToolUse)? | JSON to stdout: `{"hookSpecificOutput": {"permissionDecision": "deny", …}}` | ? |
| What are the file-editing tool names? | `Edit`, `MultiEdit`, `NotebookEdit` | ? |
| What session ID is available? | `session_id` field in hook input | ? |

### Step 3 — Write thin adapter scripts

Each hook script should follow this pattern:

```python
#!/usr/bin/env python3
import json, os, sys

_CORE = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "core"))
sys.path.insert(0, _CORE)

from brainstorm_state import read_lock, get_reminder   # import only what you need

def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception:
        return  # fail open

    session_id = data.get("session_id", "").strip()
    cwd = data.get("cwd", os.getcwd())

    if not session_id:
        return

    try:
        lock = read_lock(cwd, session_id)
        if lock:
            # agent-specific output here
            print(get_reminder(lock["topic"]))
    except Exception:
        pass  # fail open

if __name__ == "__main__":  # pragma: no cover
    main()
```

All error paths must exit cleanly (fail open). Never call `sys.exit(2)` or equivalent from an error path.

### Step 4 — Write tests

Add a test class to `tests/run_tests.py` that covers your new hook scripts. Use the same `_call_hook` / `_call_hook_raw` helpers already defined there. Aim for 100% coverage on your new code.

### Step 5 — Update the stubs

Replace the `README.md` stub in `agents/<agent-name>/` with your actual integration notes.

Update the project-level `README.md` to list your agent in the "Adding support for another agent" table.

---

## Pull request process

1. Fork the repo and create your branch from `main`
2. Run `make test` — all 150 tests must pass
3. Run `make coverage` — coverage must remain at 100%
4. Open a pull request using the [PR template](.github/PULL_REQUEST_TEMPLATE.md)
5. Describe what agent you integrated and what you had to verify about its hook system

PRs that drop test coverage will not be merged.

---

## Code standards

- **stdlib only** — no third-party dependencies, ever. `core/` must remain importable with a bare Python 3.8 install.
- **Fail open** — every hook script must exit cleanly on any error. The user should never end up with a broken Claude session because a hook crashed.
- **No global state** — all state lives in the `<project>/.claude/brainstorm/` directory. Scripts are stateless processes.
- **Atomic writes** — use `_atomic_write` (or equivalent) whenever writing lock files.
- **No comments explaining what the code does** — name things clearly instead. Comments are only for non-obvious *why* (a hidden constraint, a workaround, a deliberate design choice).

---

## Questions

Open a [Discussion](https://github.com/mehmetcanfarsak/Brainstorm-Mode/discussions) for anything that doesn't fit a bug report or feature request.
