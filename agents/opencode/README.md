# brainstorm-mode — OpenCode integration

The OpenCode integration of brainstorm-mode. Like the claude-code integration,
all state and policy live in the agent-agnostic Python core (`../../core`); the
files here are a thin adapter that translates OpenCode's plugin API to that core.

## Layout

```
opencode/
├── plugin/
│   └── brainstorm-mode.ts      # OpenCode plugin — thin shim that shells to the python adapters
├── commands/
│   ├── brainstorm.md           # /brainstorm command
│   └── brainstorm-done.md      # /brainstorm-done command
├── hooks_scripts/              # Thin python adapters → ../../core/brainstorm_state.py
│   ├── on_user_prompt.py       # chat.message            → re-inject the reminder
│   ├── on_pre_tool_use.py      # tool.execute.before     → block edit/patch
│   └── on_session_start.py     # session.compacting      → re-anchor across compaction
└── setup.sh                    # Install / uninstall (no jq needed)
```

## How OpenCode differs from Claude Code

| Concern | Claude Code | OpenCode |
|---|---|---|
| Extension mechanism | Shell hooks reading stdin JSON | TypeScript/JS plugin in `.opencode/plugins/` |
| Per-prompt injection | `UserPromptSubmit` (stdout → context) | `chat.message` (push a text part) |
| Hard tool block | `PreToolUse` deny JSON | `tool.execute.before` — **throw to block** |
| Compaction re-anchor | `SessionStart` (source=compact) | `experimental.session.compacting` (push to context) |
| File-editing tool names | `Edit`, `MultiEdit`, `NotebookEdit` | `edit`, `patch` |
| Session id / cwd for commands | `CLAUDE_SESSION_ID` / `CLAUDE_CWD` | injected via the plugin's `shell.env` hook as `BRAINSTORM_SESSION_ID` / `BRAINSTORM_CWD` |

The plugin shells out to the python adapters with `node:child_process`, so the
exact same `core/` logic — locks, TTL, drift log, pending-lock claim — backs both
agents. `write` (new files), `bash`, and `read` stay available during brainstorm
mode; only `edit` and `patch` are blocked.

## Install

```bash
# Into a specific project (creates <project>/.opencode/)
bash agents/opencode/setup.sh --project /path/to/your-project

# Globally (~/.config/opencode/, all OpenCode sessions)
bash agents/opencode/setup.sh --global
```

`setup.sh` copies the plugin and commands into OpenCode's config dirs and bakes
in absolute paths (no `${...}` placeholders left to resolve, no `jq` needed).
**Requires `python3` on `PATH`** at runtime.

Uninstall with `--uninstall`:

```bash
bash agents/opencode/setup.sh --uninstall --project /path/to/your-project
bash agents/opencode/setup.sh --uninstall --global
```

## Usage

Identical to the claude-code flow:

```
/brainstorm how should we design our caching layer?
...converse...
/brainstorm-done
```

`/brainstorm` activates the lock (the model runs `core/activate.py` via the
`bash` tool); editing is then blocked until `/brainstorm-done`, which produces the
convergence handoff and runs `core/deactivate.py` to unlock.

## Tests

- **Python adapters** are covered to 100% by the shared suite — run `make coverage`.
- **Plugin integration** (the plugin ↔ python boundary, end to end) is verified
  by `tests/opencode_smoke.ts`:

  ```bash
  bun tests/opencode_smoke.ts
  ```

  It loads the real plugin and drives every hook against the real core: activate
  → block `edit`/`patch` → allow `bash`/`write` → inject reminder → re-anchor on
  compaction → expose env → deactivate → unblock. No LLM required.
