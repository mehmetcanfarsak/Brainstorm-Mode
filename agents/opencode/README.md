# brainstorm-mode — OpenCode integration (future)

This directory will contain the OpenCode-specific integration for brainstorm-mode.

## Expected structure (when implemented)

```
opencode/
├── commands/
│   ├── brainstorm.md        # /brainstorm command definition
│   └── brainstorm-done.md   # /brainstorm-done command definition
├── hooks/
│   └── hooks.json           # OpenCode hook registrations
├── hooks_scripts/
│   ├── on_user_prompt.py    # Thin adapter → ../../core/brainstorm_state.py
│   ├── on_pre_tool_use.py
│   └── on_session_start.py
└── setup.sh
```

## Core reuse

All state management lives in `../../core/brainstorm_state.py` — the hook scripts
here are thin adapters that translate OpenCode's hook input schema to the agent-agnostic
`core/` API.

Key differences to implement vs. claude-code:
- Verify OpenCode hook event names and input JSON schema
- Verify which tool names correspond to file editing operations
- Verify the deny-decision format for blocking tool calls
- Verify the command/slash-command registration mechanism
