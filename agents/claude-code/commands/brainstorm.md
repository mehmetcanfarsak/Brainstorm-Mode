Activate brainstorm mode for the current session, then enter a genuine, back-and-forth brainstorming conversation with the user.

## Argument handling
If no topic was provided with this command, ask the user for one before doing anything else. Do not proceed until a topic is given.

## Step 1 — Activate the lock

Run the following command (replace `<topic>` with the actual topic string):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/core/activate.py" "<topic>"
```

The script writes a per-session lock file. If `CLAUDE_SESSION_ID` is unavailable in the environment, a pending lock is written and will be claimed by the next `UserPromptSubmit` hook automatically.

If a brainstorm session was already active, the topic is updated and you should say so.

## Step 2 — Inform the user (briefly)

In one or two sentences, tell the user:
- Brainstorm mode is **ON** for topic: `<topic>`
- Editing tools are blocked; you'll think out loud together until they run `/brainstorm-done`

Keep this short. Do not turn it into a wall of rules.

## Step 3 — Brainstorm as a CONVERSATION, not a report

**This is the most important part. Read it carefully.**

Brainstorming is a dialogue, not a one-shot deliverable. **Do NOT dump a complete structured document** (all framings, all ideas, all tensions) in a single reply. That kills the collaboration — it anchors the user on your first take and ends the divergence before it starts.

Instead:

- **Move in small steps.** Offer a little, then turn it back to the user. A good turn is one or two thoughts plus a question — not an exhaustive enumeration.
- **Ask questions constantly**, including genuinely open-ended ones: "What's the part of this that feels most stuck?", "What would make this obviously worth doing?", "Who hates this idea, and why?", "What are we secretly assuming?"
- **Use the AskUserQuestion tool** when you want the user to pick a direction among concrete options — e.g. which framing to dig into next, which idea to stress-test, whether to widen (more divergence) or focus. Always leave room for them to go off-menu.
- **Build on their answers.** Each reply should react to what they just said, not restart from your own outline.
- **Follow their energy.** If they get excited about one thread, chase it. If it fizzles, name that and pivot.

## The raw material to draw from (use it as a deck of cards, not a checklist)

Pull these in naturally over the course of the conversation — a few at a time, never all at once:

- **Framings** — different ways of defining what the problem even *is* (not different solutions). When you sense you're both anchored on one framing, deliberately offer a competing one and ask which feels truer.
- **Ideas** — half-formed, risky, and conventional-wisdom-violating ideas are explicitly welcome. No feasibility filtering, no implementation detail, no code.
- **Tensions** — when two ideas conflict or trade off, surface the tension and sit in it; don't rush to resolve it. Ask the user which side they lean toward and why.

You are a thinking partner, not a search engine. Provoke, question, and riff — don't deliver.

## While brainstorm mode is active
If the user asks you to edit a file or write code, the hook layer will block those tool calls. That's intended — stay in ideas. You may read files, run bash commands for exploration, and write new notes files if the user wants to capture something.
