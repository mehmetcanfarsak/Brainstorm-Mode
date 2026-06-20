# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-06-20

### Added

- **Venue presets via layered config** (academic mode) — keep a default venue
  list in `~/.config/brainstorm/config` (user-global) and/or `<project>/.brainstorm`
  (per-project), layered like `CLAUDE.md`: the two are merged (venues unioned,
  case-insensitive dedupe, global first). `/brainstorm-academic` applies the merged
  list automatically when `--venues` is omitted; pass `--venues ""` to opt out.
  New `core.load_brainstorm_config()`; config format is `key: value` lines with
  `#` comments (only `venues` is consumed today).

- **Mid-session venue amendment** (academic mode) — when the user approves a venue
  that wasn't in the original list (e.g. "papers from XYZ are fine too"), the agent
  persists it with `activate.py --add-venues "<venue>"`. `core.update_venues()`
  merges it into the active lock (case-insensitive dedupe, preserves `created_at`/
  TTL), so every subsequent per-prompt reminder reflects the broadened list instead
  of reverting to the frozen one. The academic reminder now also tells the agent to
  honor and persist user-approved venues, and the command asks up front whether the
  user wants to add any conferences/journals.

### Changed

- **Conversational pacing** (all modes) — the per-prompt reminder now instructs the
  agent to ask at most one question per reply (no rapid-fire interrogation) and to
  always offer an open-ended option (e.g. "Open — let's explore") when presenting
  choices, so the user is never boxed into the agent's framing. From user feedback.
- **Stronger citation honesty** (academic mode) — the reminder now forbids calling a
  paper influential/seminal/well-known/state-of-the-art unless verified that session,
  requires distinguishing searched-now claims from recalled ones, and requires
  labeling unverified sources (e.g. "venue unverified"). The `/brainstorm.md` and
  `/brainstorm-academic.md` commands carry matching guidance.

### Added

- **`/brainstorm-academic` command** (Claude Code + OpenCode) — literature-grounded
  research brainstorming with an enforced source-quality policy, built from
  researcher feedback. The command scopes acceptable venues up front (proposes a
  field-appropriate list to confirm/edit), stores them in the session lock
  (`"mode": "academic"`, `"venues": ...`), and the per-prompt reminder re-injects
  the full policy every turn so it cannot decay or be skipped: literature search
  before weighing in (unprompted), papers cited with authors/venue/year,
  established findings separated from open gaps, primary references restricted
  to the agreed venues, arXiv preprints only if venue-accepted or clearly from a
  credible group and directly relevant, and never workshop papers,
  non-peer-reviewed preprints, or low-tier journals as primary references.
  `/brainstorm-done` adds open research questions and a vetted reading list to
  the handoff; the archive records the venue list.
- `core/activate.py` accepts `--venues "<list>"`; pending locks preserve venues
  across the claim.

- **`/brainstorm-actionable` command** (Claude Code + OpenCode) — brainstorming for
  actionable ideas. Same enforcement as `/brainstorm` (editing blocked, per-turn
  re-injection), but the session lock carries `"mode": "actionable"` and the
  reminder steers toward concrete, feasibility-filtered ideas: constraints
  first, smallest first step + main blocker + effort guess per idea, shrink
  before dropping. `/brainstorm-done` produces an ordered action plan for these
  sessions, and the archive records the mode.
- `core/activate.py` accepts `--mode divergent|actionable`; pending locks
  preserve the mode across the claim. Old locks without a mode field are read
  as divergent (backward compatible).

- **OpenCode integration** (`agents/opencode/`) — a thin TypeScript plugin that
  reuses the same agent-agnostic `core/`:
  - `tool.execute.before` throws to hard-block the `edit` and `patch` tools.
  - `chat.message` re-injects the brainstorming reminder every turn.
  - `experimental.session.compacting` re-anchors the topic across compaction.
  - `shell.env` exposes the session id / cwd to the `/brainstorm` commands.
  - `/brainstorm` and `/brainstorm-done` commands plus a `jq`-free `setup.sh`.
- `tests/opencode_smoke.ts` — a `bun` integration smoke test that drives every
  plugin hook against the real `core/` (block / allow / inject / re-anchor /
  env / unblock), no LLM required.
- **Reminder escalation** — once a session accumulates `ESCALATION_THRESHOLD`
  (3) blocked edit attempts, the per-prompt reminder is prefixed with a sterner
  line that names the count, computed from the drift log at hook time.
- **Loud TTL expiry** — when a lock hits its 8-hour TTL, `read_lock` leaves a
  one-shot tombstone so the next prompt announces "brainstorm mode expired,
  editing unblocked" instead of silently re-enabling edits mid-session.
- **Session transcript capture** — `/brainstorm-done` archives each session to
  `.claude/brainstorm/sessions/<stamp>-<slug>.md` with topic, duration,
  blocked-edit count, the full drift-event table, and the convergence handoff
  (piped to `deactivate.py` on stdin).
- A `bun`/Python smoke run plus unit tests bring the suite to 135 tests, still
  100% line coverage; verified live end to end against OpenCode 1.17.3.

### Changed

- `core/activate.py` and `core/deactivate.py` read agent-neutral
  `BRAINSTORM_SESSION_ID` / `BRAINSTORM_CWD` env vars, falling back to the
  existing `CLAUDE_*` vars (backward compatible).
- `get_reminder(topic, drift_count=0)` gained an optional drift count; the
  `UserPromptSubmit` / `chat.message` adapters now pass it for escalation.
- `core/deactivate.py` reads an optional convergence handoff from stdin and
  archives the session before unlocking editing tools.

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

[Unreleased]: https://github.com/mehmetcanfarsak/Brainstorm-Mode/compare/v1.1.0...HEAD
[1.1.0]: https://github.com/mehmetcanfarsak/Brainstorm-Mode/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/mehmetcanfarsak/Brainstorm-Mode/releases/tag/v1.0.0
