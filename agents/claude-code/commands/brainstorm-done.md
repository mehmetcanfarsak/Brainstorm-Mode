End brainstorm mode and produce the convergence handoff summary.

**Order is mandatory: generate the summary FIRST, then deactivate.**
This ensures the handoff is produced while the agent is still constrained.

## Check for active session
If brainstorm mode is not currently active (no lock file exists for this session), say so and skip all steps below.

## Step 1 — Convergence handoff

Review all ideas raised in this brainstorm session and produce a structured handoff:

**Clusters (3–6 named clusters):**
For each cluster:
- **Summary:** one-line description of what this cluster is about
- **Strongest idea:** the single most promising idea in this cluster
- **Key risk / unknown:** the main blocker or open question for this cluster

**Recommended next step:**
Choose one of:
- "Enter plan mode with cluster `<X>`" — if one cluster is clearly the strongest path
- "More divergence needed on `<Y>`" — if key questions remain unresolved

> **Actionable sessions** (started with `/brainstorm-actionable`): structure the
> handoff as an **action plan** instead of clusters — an ordered list of ideas,
> each with its smallest first step, main blocker, and effort guess. The
> recommended next step is then simply "start with action `<N>`".

> **Academic sessions** (started with `/brainstorm-academic`): add two sections
> to the handoff — **Open research questions** (the gaps the discussion
> surfaced) and a **vetted reading list** (each entry: paper, authors, venue,
> year, one line on why it matters; only sources that pass the session's
> quality policy).

## Step 2 — Deactivate the lock (and archive the handoff)

After the summary is fully written, run the command below, **piping your handoff
markdown to it on stdin** so it is saved into the session archive. Replace the
content between the `HANDOFF` markers with the exact clusters + recommendation
you just produced:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/core/deactivate.py" <<'HANDOFF'
<paste your full convergence handoff markdown here>
HANDOFF
```

The script archives the session (topic, duration, blocked-edit count, drift
events, and your handoff) to `.claude/brainstorm/sessions/` and prints the path,
then unlocks editing.

## Step 3 — Confirm to the user

Tell the user:
- Brainstorm mode is **OFF**
- `Edit`, `MultiEdit`, and `NotebookEdit` are now **unblocked**
- Where the session was archived (the path printed by the script)
- They can enter `/plan` mode or begin implementing the chosen cluster
