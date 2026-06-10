# Pull request

## Summary

<!-- What does this PR do and why? -->

## Type of change

- [ ] Bug fix
- [ ] New agent integration (Codex, OpenCode, etc.)
- [ ] Enhancement to existing behavior
- [ ] Documentation
- [ ] Other

## If this adds or changes an agent integration

<!-- Skip if not applicable. -->

- Agent: <!-- e.g. Codex -->
- Hook event names verified: <!-- e.g. UserPromptSubmit equivalent -->
- File-editing tool names blocked: <!-- e.g. Edit, MultiEdit, NotebookEdit -->
- Deny-decision JSON shape verified against the agent's current docs: <!-- yes/no + link -->

## Checklist

- [ ] `make test` passes (all tests green)
- [ ] `make coverage` shows 100% coverage
- [ ] No third-party dependencies were added (`core/` stays stdlib-only)
- [ ] All hook scripts fail open (exit cleanly on any error)
- [ ] Updated docs / README / CHANGELOG where relevant

## Related issues

<!-- e.g. Closes #12 -->
