# brainstorm-mode — Enforce Ideation Mode in Claude Code & AI Coding Agents

[![Tests](https://github.com/mehmetcanfarsak/Brainstorm-Mode/actions/workflows/tests.yml/badge.svg)](https://github.com/mehmetcanfarsak/Brainstorm-Mode/actions/workflows/tests.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](#testing)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

A plugin for **Claude Code and OpenCode** (with a multi-agent architecture ready for Codex and others) that **blocks file-editing tools at the hook layer** and **re-injects the brainstorming constraint on every prompt** — so ideation mode survives context compaction and cannot be talked out of.

> **The core problem:** Ask an AI coding agent to brainstorm and it anchors on its first idea and starts implementing. A one-time "no code, just ideas" instruction decays as context grows and is destroyed entirely by compaction. brainstorm-mode enforces the constraint at the infrastructure level, not the prompt level.

---

## Table of contents

- [How it works](#how-it-works)
- [Why a plugin beats a brainstorming skill](#why-a-plugin-beats-a-brainstorming-skill)
- [Requirements](#requirements)
- [Installation](#installation-claude-code)
- [Usage](#usage)
- [FAQ](#faq)
- [Project structure](#project-structure)
- [The drift log](#the-drift-log-research-instrumentation)
- [Adding a new agent](#adding-support-for-a-new-agent)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

---

## How it works

brainstorm-mode uses two enforcement layers that operate independently:

### Layer 1 — Per-prompt constraint injection (soft layer)

A `UserPromptSubmit` hook fires on every user message and injects a short reminder into Claude's context window:

```
BRAINSTORM MODE ACTIVE — topic: "caching strategy". Brainstorm as a
conversation, not a report: offer a thought or two, then ask a question
back. No code, no implementation detail. Editing tools are blocked...
```

This re-injection happens *every turn*, which is what keeps the constraint alive through context compaction. Even after Claude Code summarizes the conversation, the next prompt re-establishes the mode from the lock file on disk.

### Layer 2 — Hook-level tool blocking (hard layer)

A `PreToolUse` hook fires before `Edit`, `MultiEdit`, and `NotebookEdit` tool calls. If a session lock is active, the hook returns a deny decision — Claude never executes the tool call regardless of what the model decided. `Bash` (for exploration) and `Write` (for saving brainstorm notes) are intentionally not blocked.

### State storage

A lock file at `<project>/.claude/brainstorm/locks/<session_id>.json` ties both layers together. The file persists across context compaction (same session ID) and is cleaned up automatically after 8 hours (TTL) or by `/brainstorm-done`. When the TTL is reached the next prompt announces the expiry out loud (rather than silently re-enabling edits mid-session), and repeated blocked-edit attempts escalate the reminder to a sterner wording.

---

## Why a plugin beats a brainstorming skill

Most "brainstorming mode" tools — including the popular **[Superpowers](https://github.com/obra/superpowers) `brainstorming` skill** — are **just a skill**: a Markdown file of instructions injected into the model's context that *asks* it to stay in ideation mode. That is the same prompt-level approach the constraint is supposed to fix. A skill is advice; brainstorm-mode is a **control plane**.

The difference is architectural, not cosmetic:

| | A brainstorming *skill* (e.g. Superpowers) | **brainstorm-mode** (this plugin) |
|---|---|---|
| **Enforcement layer** | Prompt / advisory text in context | `PreToolUse` **hook** — runs in the harness, outside the model |
| **Can the model ignore it?** | Yes — it's a suggestion the model may override | **No** — `Edit`/`MultiEdit`/`NotebookEdit` calls are *denied* before they run |
| **"Just make one quick edit"?** | Usually complies and drifts into building | **Blocked deterministically**, every time |
| **Survives context compaction?** | No — guidance decays and is wiped on compact | **Yes** — re-injected from disk on every turn + `SessionStart` re-anchor |
| **Where does the state live?** | In the conversation context (volatile) | On-disk lock keyed to `session_id` (durable) |
| **Survives `--resume`?** | Lost silently | Detected — you're told the prior topic and how to re-enter |
| **Measures whether it worked?** | No | **Yes** — every drift attempt is logged to `drift-log.jsonl` |
| **Talked out of the mode?** | One persuasive prompt is enough | The model **cannot disable its own hook** |
| **Setup** | Drop in a Markdown file | `/plugin install`, or one idempotent script |

### Why "just a skill" isn't enough

Execution drift is a *post-training prior*, not a misunderstanding. Coding agents are tuned to act, so a one-time "no code, just ideas" instruction loses tug-of-war against that prior as the session grows — and **context compaction deletes the instruction entirely**. A skill lives in exactly the layer that decays. You can write the most eloquent brainstorming skill in the world and the model will still, three compactions later, cheerfully start editing files.

brainstorm-mode moves the constraint to the layer the model **doesn't control**:

- **Hard layer (hooks):** the harness denies edit tools regardless of what the model "decided." Persuasion, jailbreak-style prompts, and honest mistakes all hit the same wall.
- **Soft layer (re-injection):** the reminder is rebuilt from the on-disk lock *every prompt*, so it's immune to compaction by construction — not by hoping the summary preserves it.
- **Instrumentation:** because every denied attempt is recorded, you can actually *measure* drift rate over a session instead of trusting that the guidance "probably held."

A skill is a great way to **describe** good brainstorming behavior. A plugin is the only way to **guarantee** it. brainstorm-mode is also multi-agent by design — the enforcement logic lives in an agent-agnostic `core/`, so the same guarantee extends to Codex, OpenCode, and others, not just one tool's skill format.

> **TL;DR** — A skill politely requests ideation mode and is forgotten the moment context is compacted. brainstorm-mode enforces it at the infrastructure level, survives compaction by construction, can't be talked out of, and logs every attempt to break it.

---

## Requirements

- **Python 3.8+** — stdlib only, no third-party packages
- **[jq](https://jqlang.github.io/jq/)** — used by `setup.sh` to merge hook config into `settings.json`
- **[Claude Code](https://claude.ai/code)** — for the Claude Code integration

---

## Installation (Claude Code)

### Option A — Plugin marketplace (recommended)

The simplest way. Inside Claude Code, add this repo as a plugin marketplace and install:

```
/plugin marketplace add mehmetcanfarsak/Brainstorm-Mode
/plugin install brainstorm-mode@brainstorm-mode
```

That's it — the commands and hooks are registered automatically, no `jq` or shell script needed. Manage it any time with `/plugin` (enable, disable, or uninstall).

> The format is `/plugin install <plugin>@<marketplace>`. Here both are named `brainstorm-mode` (this repo is both the marketplace and the plugin), which is why it appears twice.

To pin a specific version or branch:

```
/plugin marketplace add mehmetcanfarsak/Brainstorm-Mode#v1.0.0
```

### Option B — Install script

If you prefer a manual install (or want to vendor the plugin into a project's `.claude/`):

```bash
git clone https://github.com/mehmetcanfarsak/Brainstorm-Mode
cd Brainstorm-Mode
```

**Into a specific project:**

```bash
bash agents/claude-code/setup.sh --project /path/to/your-project
# or:
make install-project PROJECT=/path/to/your-project
```

**Globally** (all Claude Code sessions):

```bash
bash agents/claude-code/setup.sh --global
# or:
make install-global
```

The setup script:
1. Copies the command files to `<target>/.claude/commands/`, replacing the `${CLAUDE_PLUGIN_ROOT}` placeholder with the real absolute path
2. Merges the three hook registrations into `<target>/.claude/settings.json` (idempotent — safe to run multiple times)

**Install `jq` if needed:** `brew install jq` · `apt install jq` · `choco install jq`

**Uninstalling the script install:**

```bash
bash agents/claude-code/setup.sh --uninstall --project /path/to/your-project
bash agents/claude-code/setup.sh --uninstall --global
```

---

## Usage

### Starting a brainstorm session

```
/brainstorm how should we design our caching layer?
```

If no topic is given, Claude asks for one before activating. Once active:

- Claude enters a **conversational** ideation loop — not a one-shot document dump
- It offers one or two thoughts, then asks you a question back (including open-ended ones)
- It uses `AskUserQuestion` to let you steer which direction to explore
- `Edit`, `MultiEdit`, and `NotebookEdit` are blocked at the hook layer
- `Bash` and `Write` remain available for exploration and saving notes

### Brainstorming for actionable ideas

```
/brainstorm-actionable how do I grow this project's user base?
```

Same enforcement (editing stays blocked, reminder re-injected every turn), different goal: instead of pure divergence, every idea must survive a **feasibility filter** and end with a clear path to action. In this mode the agent:

- Establishes your **constraints first** — time, resources, skills, what "done" looks like
- Names, for each idea, the **smallest first step** (startable this week), the **main blocker**, and a rough **effort guess**
- **Shrinks rather than drops**: an infeasible idea becomes its "10% version" instead of dying
- Surfaces **dependencies** — which idea unblocks the others
- Ends (via `/brainstorm-done`) with an **action plan**: an ordered list of first steps rather than idea clusters

The session lock stores `"mode": "actionable"`, so the steering survives compaction exactly like the classic mode. Both modes share the same lock, drift log, escalation, TTL, and archive machinery.

### Academic research brainstorming

```
/brainstorm-academic robustness of diffusion models
```

A literature-grounded research brainstorm with an **enforced source-quality policy** — built for researchers who are tired of agents that (a) only consult the literature when explicitly told, (b) cite whatever a web search surfaces, and (c) forget the citation rules they were given three prompts ago.

At session start the agent proposes a venue list for your field (e.g. NeurIPS, ICML, ICLR, JMLR for ML) and asks you to confirm, broaden, or replace it — then bakes it into the session lock. From that point, **every prompt** re-injects:

- **Literature first, unprompted** — search published work before weighing in on any thread, even just to answer a question, and shape the discussion around what's actually published (specific papers: authors, venue, year — established findings vs. open gaps)
- **The venue restriction** — primary references only from the agreed venues
- **The preprint rule** — arXiv preprints are acceptable *only* if accepted at one of those venues or clearly from a credible group and directly relevant
- **The hard exclusions** — no workshop papers, no non-peer-reviewed preprints, no low-tier journals as primary references

This is the part a prompt or skill cannot deliver: instructions like these normally decay as the session grows and vanish at compaction — which is precisely when low-quality citations creep back in. Here the policy lives in the on-disk lock and re-arrives with every turn, so **it cannot be skipped, forgotten, or compacted away**. `/brainstorm-done` closes with open research questions and a vetted reading list, archived to disk.

Two conveniences for venues:

- **Add mid-session.** Approve a venue that wasn't on the list ("papers from XYZ are fine too") and the agent persists it — every later prompt reflects the broadened list, without resetting the session.
- **Saved presets, layered like `CLAUDE.md`.** Keep a default venue list in a config file so you don't re-type it each session. Two locations are merged (per-project augments user-global):

  ```
  # ~/.config/brainstorm/config   — your field's defaults, all projects
  venues: NeurIPS, ICML, ICLR, JMLR, TPAMI

  # <project>/.brainstorm          — extra venues for this project (unioned in)
  venues: CVPR, ICCV
  ```

  `/brainstorm-academic` applies the merged list automatically when you don't pass an explicit list; the agent just shows it and asks whether to add anything. (Format: `key: value` lines, `#` comments; only `venues` is used today.)

### Ending a brainstorm session

```
/brainstorm-done
```

This produces a **convergence handoff** *before* unlocking tools:

1. **Clusters** — 3–6 named idea clusters, each with: a one-line summary, the strongest idea in the cluster, and the key risk or unknown
2. **Recommended next step** — either "enter plan mode with cluster X" or "more divergence needed on Y"
3. **Archive** — the session is written to `.claude/brainstorm/sessions/<date>-<topic>.md` with the topic, duration, blocked-edit count, the full drift-event table, and your convergence handoff
4. **Unlock** — the lock file is deleted, editing tools become available again

> Order is enforced by the command: summary first, deactivation second — the handoff is generated while the agent is still constrained, then archived as a durable artifact before tools unlock.

### Re-activating after context compaction

brainstorm-mode survives compaction automatically. After a compact event:
- The `SessionStart` hook re-injects a one-line anchor
- The per-prompt hook picks up normally on the next message
- No action required from you

### After `--resume` (new session)

`--resume` creates a new session ID, so the mode drops (fail-safe: you get full tool access rather than a mysteriously broken session). The `SessionStart` hook notifies you:

```
A brainstorm session on 'caching strategy' was active before resume.
Brainstorm mode is NOT currently active; run /brainstorm caching strategy to re-enter.
```

---

## FAQ

**Q: Why does the AI keep starting to implement things during brainstorming?**

This is execution drift — a well-documented behaviour in instruction-tuned coding agents. Post-training on coding tasks creates a strong prior toward action. brainstorm-mode counteracts this with repeated constraint injection (soft layer) and deterministic tool blocking (hard layer).

**Q: Does brainstorm-mode work after Claude Code compacts the conversation?**

Yes. State lives in a disk-based lock file keyed to the session ID, not in the conversation context. The `UserPromptSubmit` hook re-injects the constraint from disk on every turn, so compaction doesn't break the mode.

**Q: Can I still read files and run shell commands during brainstorming?**

Yes. `Read`, `Bash`, `Glob`, `Grep`, `WebSearch`, and `WebFetch` are all allowed. Only the three file-editing tools are blocked: `Edit`, `MultiEdit`, and `NotebookEdit`. `Write` is also allowed so you can save brainstorm notes to new files.

**Q: What happens if I ask Claude to "just make a quick edit" while brainstorming?**

The `PreToolUse` hook denies the `Edit` (or `MultiEdit`) call before it executes. Claude sees a deny decision and responds with ideas or design notes instead. The denied attempt is also logged to the drift log.

**Q: Can Claude talk itself out of brainstorm mode?**

No. The hard layer (hook-level blocking) operates independently of the model's decisions. Even if Claude is convinced to attempt a file edit, the hook denies it. The model cannot disable its own hook.

**Q: Does brainstorm-mode work with agents other than Claude Code?**

Yes — **Claude Code and OpenCode** are both supported (see [agents/opencode/](agents/opencode/)). The `core/` module is agent-agnostic; each agent is a thin adapter in `agents/<name>/` that translates its extension API to `core/` without touching the core logic. Codex is stubbed and ready for the same treatment.

**Q: What is the drift log?**

Every denied tool call is appended to `<project>/.claude/brainstorm/drift-log.jsonl`. This is research instrumentation for measuring execution-drift rate over time — how often the agent attempts to execute despite an active, freshly-injected constraint.

**Q: How do I add brainstorm-mode to my own Claude Code project?**

Run `bash agents/claude-code/setup.sh --project /path/to/your-project`. This requires `jq`.

**Q: Is there a global install option?**

Yes: `bash agents/claude-code/setup.sh --global` installs for all Claude Code sessions via `~/.claude/settings.json`.

**Q: Does this work with Claude Code's built-in plan mode?**

brainstorm-mode does not modify or interact with Claude Code's built-in plan mode. They are independent. `/brainstorm-done` ends with a "recommended next step" that often suggests entering plan mode.

---

## Project structure

```
Brainstorm-Mode/
│
├── core/                              # Agent-agnostic logic — no agent dependencies
│   ├── brainstorm_state.py            # Lock R/W, TTL expiry, drift log, pending-lock
│   ├── activate.py                    # Called by /brainstorm command
│   └── deactivate.py                  # Called by /brainstorm-done command
│
├── agents/                            # One subdirectory per supported agent
│   ├── claude-code/                   # Claude Code integration (v1)
│   │   ├── commands/
│   │   │   ├── brainstorm.md          # /brainstorm slash command definition
│   │   │   ├── brainstorm-actionable.md  # /brainstorm-actionable (actionable mode)
│   │   │   ├── brainstorm-academic.md # /brainstorm-academic (literature-grounded)
│   │   │   └── brainstorm-done.md     # /brainstorm-done slash command definition
│   │   ├── hooks/
│   │   │   └── hooks.json             # Hook registrations for the plugin manifest
│   │   ├── hooks_scripts/             # Thin adapters that call into core/
│   │   │   ├── on_user_prompt.py      # UserPromptSubmit hook
│   │   │   ├── on_pre_tool_use.py     # PreToolUse hook (blocks Edit/MultiEdit/NotebookEdit)
│   │   │   └── on_session_start.py    # SessionStart hook (compact re-anchor / resume notice)
│   │   └── setup.sh                   # Install / uninstall script
│   │
│   ├── opencode/                      # OpenCode integration (TS plugin → core/)
│   │   ├── plugin/brainstorm-mode.ts  # Thin plugin: throw-to-block, inject, re-anchor
│   │   ├── commands/                  # /brainstorm, /brainstorm-done
│   │   ├── hooks_scripts/             # Thin adapters that call into core/
│   │   └── setup.sh                   # Install / uninstall (no jq needed)
│   │
│   └── codex/README.md                # Stub — ready for Codex integration
│
├── tests/
│   ├── fixtures/                      # Example hook-input JSON for manual testing
│   └── run_tests.py                   # 185 tests, 100% line coverage, stdlib only
│
├── .claude-plugin/
│   ├── plugin.json                    # Claude Code plugin manifest
│   └── marketplace.json               # Marketplace catalog (enables /plugin install)
├── .github/                           # CI workflow, issue templates, PR template
│
├── Makefile                           # test, coverage, install-project, install-global
├── llms.txt                           # LLM-readable project summary
├── CONTRIBUTING.md
├── CHANGELOG.md
├── SECURITY.md
└── LICENSE
```

### Multi-agent architecture

All state management is in `core/` with zero knowledge of any specific agent. `agents/<name>/` contains only thin adapters — hook scripts that translate the agent's hook input format into `core/` API calls. Adding a new agent means:

1. Create `agents/<agent-name>/` with commands, hooks config, and thin hook scripts
2. Call the existing `core/` API — no changes to `core/` needed
3. Write tests for your adapter scripts

---

## The drift log (research instrumentation)

Every denied tool call is appended to `<project>/.claude/brainstorm/drift-log.jsonl`:

```json
{
  "ts": "2026-01-15T14:32:07.123+00:00",
  "session_id": "abc-123",
  "topic": "caching strategy",
  "tool_name": "Edit",
  "minutes_since_activation": 14.2,
  "post_compaction": false
}
```

Each record is a timestamped instance of the agent attempting execution despite an active, freshly-injected constraint. The log enables questions like:

- Does execution-drift rate grow with session length?
- Does it spike after context compaction?
- Does per-prompt injection reduce drift rate compared to a one-time instruction?

The schema is intentionally stable to support longitudinal analysis across sessions.

---

## Lock file schema

Lock files live at `<project>/.claude/brainstorm/locks/<session_id>.json` and are gitignored.

```json
{
  "session_id": "abc-123",
  "topic": "caching strategy",
  "mode": "divergent",
  "created_at": "2026-01-15T14:17:52.441+00:00",
  "ttl_hours": 8
}
```

A lock is active iff the file exists, parses correctly, `session_id` matches the current hook input, and `now < created_at + ttl_hours`. Expired or corrupt files are deleted on next read.

---

## Adding support for a new agent

The `core/` public API is the contract between the agent-agnostic layer and agent-specific adapters:

```python
from brainstorm_state import (
    read_lock,           # check whether mode is active for a session_id
    write_lock,          # activate brainstorm mode
    delete_lock,         # deactivate brainstorm mode
    write_pending_lock,  # activate when session_id is not yet available
    claim_pending_lock,  # promote a pending lock to a real session lock
    cleanup_old_locks,   # sweep files older than 7 days (call occasionally)
    set_compact_flag,    # record that a compaction event occurred
    is_post_compact,     # check the compaction flag
    append_drift_log,    # record a denied tool call
    get_reminder,        # get the per-prompt reminder string
    find_recent_lock,    # scan for any active lock across sessions
    BLOCKED_TOOLS,       # frozenset — the tools to block for your agent
)
```

Key things to verify for each new agent: hook event names, tool name strings, the JSON shape for denying a tool call in `PreToolUse`, and how session ID is delivered. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

---

## Testing

```bash
make test       # run all 185 tests (no extra dependencies)
make coverage   # run tests and print line coverage (100%)
make clean      # remove __pycache__ and coverage artifacts
```

Tests call `main()` directly via import with mocked `sys.stdin`/`sys.stdout` — no subprocesses needed for coverage measurement. A separate `TestSubprocessSmoke` class verifies the scripts work correctly as standalone CLI programs. No third-party test dependencies.

---

## Contributing

Contributions are welcome — especially new agent integrations. Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.

---

## Security

See [SECURITY.md](SECURITY.md) for how to report vulnerabilities responsibly.

---

## License

MIT © 2026 [Mehmet Can Farsak](https://github.com/mehmetcanfarsak)

---

## Related topics

`claude-code` · `claude-code-plugin` · `ai-coding-agent` · `brainstorming` · `ideation` · `llm-hooks` · `context-compaction` · `execution-drift` · `pretooluse-hook` · `ai-productivity`
