Activate **academic** brainstorm mode for the current session: a literature-grounded research brainstorm where every thread is anchored to published, peer-reviewed work and sources are vetted against a strict quality policy.

Editing tools stay blocked throughout, and the venue policy below is stored in the session lock and re-injected on **every** prompt — it cannot decay, be forgotten, or be skipped.

## Argument handling
If no topic was provided with this command, ask the user for one before doing anything else. Do not proceed until a topic is given.

## Step 1 — Scope the venues BEFORE activating

Before anything else, establish which venues count as acceptable primary references. Propose a concrete list appropriate to the topic's field, **then explicitly ask whether there are any other conferences or journals they'd like to add** — use `AskUserQuestion` with options like:

- **"Use this list"** — your proposed top venues for the field (e.g. for ML: NeurIPS, ICML, ICLR, JMLR, TPAMI; adapt to the actual field)
- **"Add some"** — the user names extra venues to append to your list
- **"Let me specify"** — the user gives their own list instead
- **"No venue list"** — rely on the general quality policy only

Keep it to this one question — don't interrogate.

## Step 2 — Activate the lock

Run the following command (replace placeholders; omit `--venues` if the user chose no list):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/core/activate.py" --mode academic --venues "<comma-separated venues>" "<topic>"
```

The venue list is baked into the per-session lock, so the source-quality policy re-arrives with every single prompt for the rest of the session.

**If the user broadens the venues mid-session** (e.g. "papers from XYZ are fine too"), honor it right away and persist it so it survives — run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/core/activate.py" --add-venues "<the new venue(s)>"
```

This merges them into the active lock without resetting the session, so every later prompt reflects the broadened list.

## Step 3 — Inform the user (briefly)

One or two sentences: academic brainstorm mode is **ON** for the topic, primary references are restricted to the agreed venues, editing tools are blocked until `/brainstorm-done`.

## Step 4 — Literature first, always

**This is the defining behavior of this mode.** Ground the discussion in the literature *proactively* — never wait to be asked:

- **Search before you speak.** Before weighing in on any thread — even just to answer a question — search for relevant published work (`WebSearch`/`WebFetch`) and shape your contribution around what you find.
- **Anchor every idea to specific papers**: authors, venue, year. "There's a line of work on X (Smith et al., NeurIPS 2024) that found Y" — not vague gestures at "the literature."
- **Separate established findings from open gaps**, and say explicitly which is which. The most valuable brainstorm output is often the gap.
- **Build the discussion on top of the papers**: when the user proposes an idea, check it against published work — has it been done? partially? what's adjacent?

## Step 5 — Source quality policy (non-negotiable)

Vet **every** source against this policy before citing it:

- Primary references must be **peer-reviewed work from the agreed venues** (or comparably reputable ones if no list was set).
- **Preprints on arXiv are acceptable only if they have been accepted to one of these venues or are clearly from a credible group and directly relevant.**
- **Do not cite workshop papers, non-peer-reviewed preprints, or low-tier journals as primary references.** They may be mentioned only as secondary context, clearly labeled as such.
- **Never call a paper influential, seminal, well-known, or state-of-the-art unless you verified that this session** (e.g. citation counts, downstream uptake, acceptance). Say whether a claim comes from a search you just ran or from prior knowledge — don't state recalled impression as fact.
- If you cannot verify a paper's venue or acceptance status, say so rather than presenting it as solid (e.g. "most relevant preprint found, venue unverified").

## Step 6 — Still a conversation

Brainstorm as a dialogue, not a literature survey dump: a finding or two plus a thought, then a question back. Use `AskUserQuestion` to let the user pick which thread to deepen. Use `Write` to save a running reading list to a notes file if the user wants one.

## While this mode is active
If the user asks you to edit a file or write code, the hook layer will block those tool calls. That's intended — capture implementation thoughts as research notes instead. `/brainstorm-done` will produce a handoff with idea clusters, open research questions, and a vetted reading list.
