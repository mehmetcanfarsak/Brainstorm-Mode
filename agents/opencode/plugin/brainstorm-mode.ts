/**
 * brainstorm-mode — OpenCode plugin (thin adapter).
 *
 * All state and policy live in the agent-agnostic Python core (../../core),
 * exactly as the claude-code integration does. This plugin only marshals
 * OpenCode hook data to the Python adapter scripts in ../hooks_scripts and
 * applies their result:
 *
 *   tool.execute.before              → throw to hard-block `edit` / `patch`
 *   chat.message                     → inject the per-turn reminder
 *   experimental.session.compacting  → re-anchor the topic across compaction
 *   shell.env                        → expose session id / cwd to /brainstorm commands
 *
 * Compatible with both Bun (OpenCode's runtime) and Node — it shells out with
 * node:child_process and avoids OpenCode-only APIs so it can be smoke-tested
 * standalone (see tests/opencode_smoke.ts).
 */
import { spawnSync } from "node:child_process"
import { join } from "node:path"

// setup.sh rewrites the placeholder below with an absolute path. When the
// placeholder is left untouched (running straight from the repo, or under the
// smoke test) it collapses to "" and we fall back to BRAINSTORM_SCRIPTS_DIR or
// a path resolved relative to this file.
const INSTALLED_DIR = "__BRAINSTORM_SCRIPTS_DIR__".replace(/^__.*__$/, "")
const SCRIPTS_DIR =
  process.env.BRAINSTORM_SCRIPTS_DIR ||
  INSTALLED_DIR ||
  join(import.meta.dirname, "..", "hooks_scripts")

function runPy(script: string, payload: Record<string, unknown>): string {
  try {
    const res = spawnSync("python3", [join(SCRIPTS_DIR, script)], {
      input: JSON.stringify(payload),
      encoding: "utf8",
    })
    return (res.stdout || "").trim()
  } catch {
    return ""
  }
}

export const BrainstormMode = async ({ directory }: { directory?: string } = {}) => {
  const cwd = directory || process.cwd()

  return {
    // Soft layer: re-inject the constraint on every user message.
    "chat.message": async (input: any, output: any) => {
      const reminder = runPy("on_user_prompt.py", { session_id: input?.sessionID, cwd })
      if (reminder) output.parts.push({ type: "text", text: reminder })
    },

    // Hard layer: deny edits deterministically, regardless of what the model decided.
    "tool.execute.before": async (input: any) => {
      const reason = runPy("on_pre_tool_use.py", {
        session_id: input?.sessionID,
        cwd,
        tool_name: input?.tool,
      })
      if (reason) throw new Error(reason)
    },

    // Survive compaction: push a topic anchor into the retained context.
    "experimental.session.compacting": async (input: any, output: any) => {
      const anchor = runPy("on_session_start.py", {
        session_id: input?.sessionID,
        cwd,
        source: "compact",
      })
      if (anchor) output.context.push(anchor)
    },

    // Expose session id + cwd to the /brainstorm and /brainstorm-done commands,
    // which shell out to core/activate.py and core/deactivate.py.
    "shell.env": async (input: any, output: any) => {
      if (input?.sessionID) output.env.BRAINSTORM_SESSION_ID = input.sessionID
      output.env.BRAINSTORM_CWD = input?.cwd || cwd
    },
  }
}
