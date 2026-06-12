---
description: End brainstorm mode and produce the convergence handoff
---

End brainstorm mode and produce the convergence handoff summary.

**Order is mandatory: generate the summary FIRST, then deactivate.**
This ensures the handoff is produced while the agent is still constrained. Do
NOT run the deactivate command until after the summary is fully written.

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
- "Begin planning/implementing cluster `<X>`" — if one cluster is clearly the strongest path
- "More divergence needed on `<Y>`" — if key questions remain unresolved

> **Actionable sessions** (started with `/brainstorm-actionable`): structure the
> handoff as an **action plan** instead of clusters — an ordered list of ideas,
> each with its smallest first step, main blocker, and effort guess. The
> recommended next step is then simply "start with action `<N>`".

## Step 2 — Deactivate the lock (and archive the handoff)

Only after the summary is fully written, run this with the `bash` tool, **piping
your handoff markdown on stdin** so it is saved into the session archive.
Replace the content between the `HANDOFF` markers with the clusters +
recommendation you just produced:

```bash
python3 "__BRAINSTORM_ROOT__/core/deactivate.py" <<'HANDOFF'
<paste your full convergence handoff markdown here>
HANDOFF
```

Session id and working directory are supplied by the plugin's `shell.env` hook.
The script archives the session (topic, duration, blocked-edit count, drift
events, and your handoff) to `.claude/brainstorm/sessions/` and prints the path.

## Step 3 — Confirm to the user

Tell the user:
- Brainstorm mode is **OFF**
- The `edit` and `patch` tools are now **unblocked**
- Where the session was archived (the path printed by the script)
- They can begin implementing the chosen cluster
