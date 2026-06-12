---
description: Activate actionable brainstorm mode (enforced ideation aimed at concrete, doable ideas)
---

Activate **actionable** brainstorm mode for the current session, then brainstorm with the user for ideas they can actually act on — concrete, scoped, feasible.

The topic is: $ARGUMENTS

This differs from `/brainstorm` (pure divergence): here every idea must survive a feasibility filter and end with a clear first step. It is still brainstorming — the `edit` and `patch` tools stay blocked the whole time.

## Argument handling
If no topic was provided (the line above is empty), ask the user for one before doing anything else. Do not proceed until a topic is given.

## Step 1 — Activate the lock

Run the following with the `bash` tool (substitute the real topic string):

```bash
python3 "__BRAINSTORM_ROOT__/core/activate.py" --mode actionable "<topic>"
```

The script writes a per-session lock file with `mode: actionable`. Session id and
working directory are provided through the plugin's `shell.env` hook
(`BRAINSTORM_SESSION_ID` / `BRAINSTORM_CWD`); if they are unavailable, a pending
lock is written and claimed automatically on your next message. If a brainstorm
session was already active, the topic/mode is updated — say so.

## Step 2 — Inform the user (briefly)

In one or two sentences, tell the user:
- Actionable brainstorm mode is **ON** for the topic
- Editing tools (`edit`, `patch`) are blocked; you'll work toward concrete, doable ideas until they run `/brainstorm-done`

Keep this short.

## Step 3 — Establish constraints FIRST

Before generating ideas, ask about the real-world envelope:
- How much **time/effort** can they realistically spend?
- What **resources/skills** are available — and what's off the table?
- What does "done" look like — what would make an idea obviously worth acting on?

Don't interrogate; two or three quick questions, then move.

## Step 4 — Brainstorm as a CONVERSATION, biased toward action

Still a dialogue, not a report — small steps, one or two ideas per turn, question back. But unlike pure divergence:

- **Every idea must be actionable.** For each one, name: the **smallest first step** (something startable this week), the **main blocker or unknown**, and a rough **effort guess** (hours / days / weeks).
- **Filter for feasibility out loud.** If an idea is exciting but infeasible under their constraints, say so and either shrink it to a feasible version or drop it.
- **Prefer shrinking over dropping.** "What's the 10% version of this?" is a core move.
- **Sequence matters.** When two ideas compete, ask which unblocks more later — surface dependencies.

No code and no file edits. You may read files and run `bash` to check feasibility facts (does X exist? how big is Y?), and use `write` to capture an action list into a new notes file if the user wants.

## While this mode is active
If the user asks you to edit a file, the plugin's hook layer will block the `edit` and `patch` tools. That's intended — capture it as an action item instead ("first step: make change X to file Y"), to be executed after `/brainstorm-done`.
