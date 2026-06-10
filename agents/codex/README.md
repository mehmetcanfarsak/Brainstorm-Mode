# brainstorm-mode — Codex integration (future)

This directory will contain the Codex-specific integration for brainstorm-mode.

## Expected structure (when implemented)

```
codex/
├── commands/
│   ├── brainstorm.md        # /brainstorm command definition
│   └── brainstorm-done.md   # /brainstorm-done command definition
├── hooks/
│   └── hooks.json           # Codex hook registrations
├── hooks_scripts/
│   ├── on_user_prompt.py    # Thin adapter → ../../core/brainstorm_state.py
│   ├── on_pre_tool_use.py
│   └── on_session_start.py
└── setup.sh
```

## Core reuse

All state management lives in `../../core/brainstorm_state.py` — the hook scripts
here are thin adapters that translate Codex's hook input schema to the agent-agnostic
`core/` API.

Key differences to implement vs. claude-code:
- Verify Codex hook event names and input JSON schema
- Verify the tool names that correspond to file editing (may differ from Edit/MultiEdit/NotebookEdit)
- Verify the deny-decision JSON shape for PreToolUse equivalent
- Verify how commands (slash or otherwise) are registered and invoked
