# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅        |

## Reporting a vulnerability

Please **do not open a public issue** for security vulnerabilities.

Instead, report privately using GitHub's [private vulnerability reporting](https://github.com/mehmetcanfarsak/Brainstorm-Mode/security/advisories/new) (Security → Report a vulnerability).

When reporting, include:

- A description of the vulnerability and its impact
- Steps to reproduce
- Affected file(s) or component(s)
- Any suggested fix, if you have one

You can expect an initial response within **7 days**. Once the issue is confirmed,
a fix will be prioritized and you'll be credited in the release notes (unless you
prefer to remain anonymous).

## Scope and threat model

brainstorm-mode is a local plugin. It runs hook scripts that:

- Read JSON from stdin (hook input)
- Read and write files under `<project>/.claude/brainstorm/`
- Make no network calls, spawn no daemons, and run no background processes

Relevant security considerations:

- **Hook scripts fail open.** On any error, they exit cleanly and allow normal
  agent behavior. A crash never blocks the user, but it also means a broken hook
  silently stops enforcing brainstorm mode — verify hooks are working if
  enforcement matters to you.
- **The hard block is a guardrail, not a sandbox.** It denies `Edit`, `MultiEdit`,
  and `NotebookEdit` tool calls. It is not a security boundary and should not be
  relied on to contain an actively adversarial agent — `Bash` and `Write` remain
  available by design.
- **Lock and log files** are written under the project's `.claude/` directory.
  Treat that directory like any other project-local state; the drift log may
  contain brainstorm topic strings.

## Out of scope

- Vulnerabilities in Claude Code itself (report to Anthropic)
- Vulnerabilities in `jq`, Python, or other system dependencies
