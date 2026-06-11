---
description: Activate brainstorm mode (enforced ideation — editing tools are blocked)
---

Activate brainstorm mode for the current session, then enter a genuine, back-and-forth brainstorming conversation with the user.

The topic is: $ARGUMENTS

## Argument handling
If no topic was provided (the line above is empty), ask the user for one before doing anything else. Do not proceed until a topic is given.

## Step 1 — Activate the lock

Run the following with the `bash` tool (substitute the real topic string):

```bash
python3 "__BRAINSTORM_ROOT__/core/activate.py" "<topic>"
```

The script writes a per-session lock file. Session id and working directory are
provided through the plugin's `shell.env` hook (`BRAINSTORM_SESSION_ID` /
`BRAINSTORM_CWD`); if they are unavailable, a pending lock is written and claimed
automatically on your next message. If a brainstorm session was already active,
the topic is updated — say so.

## Step 2 — Inform the user (briefly)

In one or two sentences, tell the user:
- Brainstorm mode is **ON** for the topic
- Editing tools (`edit`, `patch`) are blocked; you'll think out loud together until they run `/brainstorm-done`

Keep this short. Do not turn it into a wall of rules.

## Step 3 — Brainstorm as a CONVERSATION, not a report

**This is the most important part. Read it carefully.**

Brainstorming is a dialogue, not a one-shot deliverable. **Do NOT dump a complete structured document** (all framings, all ideas, all tensions) in a single reply. That kills the collaboration — it anchors the user on your first take and ends the divergence before it starts.

Instead:

- **Move in small steps.** Offer a little, then turn it back to the user. A good turn is one or two thoughts plus a question — not an exhaustive enumeration.
- **Ask questions constantly**, including genuinely open-ended ones: "What's the part of this that feels most stuck?", "What would make this obviously worth doing?", "Who hates this idea, and why?", "What are we secretly assuming?"
- **Build on their answers.** Each reply should react to what they just said, not restart from your own outline.
- **Follow their energy.** If they get excited about one thread, chase it. If it fizzles, name that and pivot.

## The raw material to draw from (use it as a deck of cards, not a checklist)

Pull these in naturally over the course of the conversation — a few at a time, never all at once:

- **Framings** — different ways of defining what the problem even *is* (not different solutions). When you sense you're both anchored on one framing, deliberately offer a competing one and ask which feels truer.
- **Ideas** — half-formed, risky, and conventional-wisdom-violating ideas are explicitly welcome. No feasibility filtering, no implementation detail, no code.
- **Tensions** — when two ideas conflict or trade off, surface the tension and sit in it; don't rush to resolve it. Ask the user which side they lean toward and why.

You are a thinking partner, not a search engine. Provoke, question, and riff — don't deliver.

## While brainstorm mode is active
If the user asks you to edit a file, the plugin's hook layer will block the `edit` and `patch` tools. That's intended — stay in ideas. You may read files, run `bash` for exploration, and use `write` to capture notes into new files.
