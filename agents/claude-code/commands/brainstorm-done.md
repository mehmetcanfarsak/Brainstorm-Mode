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

## Step 2 — Deactivate the lock

After the summary is fully written, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/core/deactivate.py"
```

## Step 3 — Confirm to the user

Tell the user:
- Brainstorm mode is **OFF**
- `Edit`, `MultiEdit`, and `NotebookEdit` are now **unblocked**
- They can enter `/plan` mode or begin implementing the chosen cluster
