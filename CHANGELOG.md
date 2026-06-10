# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-06-10

### Added

- **Brainstorm mode for Claude Code** with two enforcement layers:
  - Soft layer: a `UserPromptSubmit` hook re-injects the brainstorming constraint
    on every prompt, so it survives context compaction.
  - Hard layer: a `PreToolUse` hook deterministically blocks `Edit`, `MultiEdit`,
    and `NotebookEdit` while a session lock is active.
- `/brainstorm <topic>` command — activates mode and begins a conversational,
  question-driven ideation loop (framings, ideas, tensions) using `AskUserQuestion`.
- `/brainstorm-done` command — produces a clustered convergence handoff first,
  then deactivates the lock and unblocks editing tools.
- `SessionStart` hook handling for `compact` (re-anchor) and `resume` (notice).
- Per-session lock files with an 8-hour TTL, atomic writes, opportunistic cleanup
  of expired/corrupt locks, and a 7-day sweep of stale files.
- Pending-lock mechanism: when the session ID is unavailable at command time, a
  pending lock is written and claimed by the next `UserPromptSubmit` hook.
- **Drift log** (`drift-log.jsonl`) — research instrumentation recording every
  denied tool call with timestamp, topic, minutes since activation, and a
  post-compaction flag.
- **Multi-agent architecture**: agent-agnostic logic in `core/`, with thin
  per-agent adapters in `agents/<name>/`. Claude Code integration is complete;
  Codex and OpenCode stubs are included.
- Claude Code plugin **marketplace distribution** via `.claude-plugin/marketplace.json`,
  installable with `/plugin marketplace add` + `/plugin install`.
- Idempotent `setup.sh` installer with `--project`, `--global`, and `--uninstall`.
- Test suite: 78 tests, 100% line coverage, stdlib `unittest` only.
- Project docs and metadata: README, CONTRIBUTING, SECURITY, LICENSE (MIT),
  `llms.txt`, `CITATION.cff`, GitHub issue/PR templates, and a CI workflow
  testing Python 3.8–3.13.

[Unreleased]: https://github.com/mehmetcanfarsak/Brainstorm-Mode/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/mehmetcanfarsak/Brainstorm-Mode/releases/tag/v1.0.0
