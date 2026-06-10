# Repository metadata (for maximum discoverability)

GitHub's repository **description** and **topics** are the single biggest levers
for GitHub search ranking and for surfacing in Google / LLM search results.
They are stored in GitHub's settings, not in the repo files, so apply them once
after pushing.

## Recommended description

Paste into **Settings → General → Description**, or the "About" sidebar on the
repo home page:

```
Enforce brainstorm mode in Claude Code & AI coding agents — block file-editing tools at the hook layer and re-inject the constraint every prompt so it survives context compaction.
```

## Recommended website

Set the "About" website field to the docs anchor:

```
https://github.com/mehmetcanfarsak/Brainstorm-Mode#readme
```

## Recommended topics

Add via the "About" gear → Topics. GitHub allows up to 20; these are ordered by
search value:

```
claude-code
claude-code-plugin
ai-coding-agent
brainstorming
ideation
llm
llm-hooks
ai-agents
context-compaction
execution-drift
pretooluse-hook
anthropic
developer-tools
ai-productivity
prompt-engineering
python
```

## Apply with the GitHub CLI

Once `gh` is installed and authenticated (`gh auth login`):

```bash
gh repo edit mehmetcanfarsak/Brainstorm-Mode \
  --description "Enforce brainstorm mode in Claude Code & AI coding agents — block file-editing tools at the hook layer and re-inject the constraint every prompt so it survives context compaction." \
  --homepage "https://github.com/mehmetcanfarsak/Brainstorm-Mode#readme" \
  --add-topic claude-code,claude-code-plugin,ai-coding-agent,brainstorming,ideation,llm,llm-hooks,ai-agents,context-compaction,execution-drift,pretooluse-hook,anthropic,developer-tools,ai-productivity,prompt-engineering,python
```

## Other discoverability checklist

- [ ] Set description + topics (above)
- [ ] Enable **Discussions** (referenced by CONTRIBUTING.md and issue template config)
- [ ] Add a social preview image (Settings → General → Social preview) — drives click-through from search and social shares
- [ ] After first release, create a GitHub **Release** tagged `v1.0.0` (Releases are indexed and rank well)
- [ ] Confirm `llms.txt` is served at the repo root (already present) for LLM crawlers
