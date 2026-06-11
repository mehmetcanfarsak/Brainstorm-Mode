/**
 * OpenCode plugin integration smoke test.
 *
 * Loads the real plugin (agents/opencode/plugin/brainstorm-mode.ts) and drives
 * each hook against the real Python core — no LLM required. Verifies the
 * plugin↔python boundary end to end: activate → block edit / allow bash /
 * inject reminder / re-anchor on compaction / expose env → deactivate → unblock.
 *
 * Run with:  bun tests/opencode_smoke.ts
 */
import { spawnSync } from "node:child_process"
import { mkdtempSync, rmSync } from "node:fs"
import { tmpdir } from "node:os"
import { join, dirname } from "node:path"
import { fileURLToPath } from "node:url"

const HERE = dirname(fileURLToPath(import.meta.url))
const REPO = join(HERE, "..")
const SCRIPTS_DIR = join(REPO, "agents", "opencode", "hooks_scripts")
const CORE = join(REPO, "core")

// Point the plugin at the in-repo python adapters.
process.env.BRAINSTORM_SCRIPTS_DIR = SCRIPTS_DIR

const { BrainstormMode } = await import(
  join(REPO, "agents", "opencode", "plugin", "brainstorm-mode.ts")
)

let failures = 0
function check(name: string, cond: boolean) {
  console.log(`${cond ? "  ok  " : " FAIL "} ${name}`)
  if (!cond) failures++
}

const SESSION = "smoke-session"
const cwd = mkdtempSync(join(tmpdir(), "bm-oc-"))

function py(script: string, args: string[], extraEnv: Record<string, string> = {}) {
  return spawnSync("python3", [join(CORE, script), ...args], {
    encoding: "utf8",
    env: { ...process.env, BRAINSTORM_SESSION_ID: SESSION, BRAINSTORM_CWD: cwd, ...extraEnv },
  })
}

try {
  const hooks = await BrainstormMode({ directory: cwd })

  // 1) Activate via the real command path (core/activate.py + agent-neutral env).
  const act = py("activate.py", ["caching strategy"])
  check("activate.py exits 0", act.status === 0)

  // 2) chat.message injects the reminder.
  const out1: any = { parts: [] }
  await hooks["chat.message"]({ sessionID: SESSION }, out1)
  check(
    "chat.message injects reminder",
    out1.parts.length === 1 && out1.parts[0].text.includes("BRAINSTORM MODE ACTIVE"),
  )

  // 3) tool.execute.before blocks `edit`.
  let threw = false
  try {
    await hooks["tool.execute.before"]({ tool: "edit", sessionID: SESSION }, { args: {} })
  } catch (e: any) {
    threw = true
    check("edit deny reason mentions topic", String(e.message).includes("caching strategy"))
  }
  check("tool.execute.before throws on edit", threw)

  // 4) tool.execute.before blocks `patch`.
  let threwPatch = false
  try {
    await hooks["tool.execute.before"]({ tool: "patch", sessionID: SESSION }, { args: {} })
  } catch {
    threwPatch = true
  }
  check("tool.execute.before throws on patch", threwPatch)

  // 5) tool.execute.before allows `bash` and `write`.
  let threwAllowed = false
  try {
    await hooks["tool.execute.before"]({ tool: "bash", sessionID: SESSION }, { args: {} })
    await hooks["tool.execute.before"]({ tool: "write", sessionID: SESSION }, { args: {} })
  } catch {
    threwAllowed = true
  }
  check("bash + write are allowed (no throw)", !threwAllowed)

  // 6) compaction re-anchor pushes context.
  const out2: any = { context: [] }
  await hooks["experimental.session.compacting"]({ sessionID: SESSION }, out2)
  check(
    "compacting pushes anchor",
    out2.context.length === 1 && out2.context[0].includes("caching strategy"),
  )

  // 7) shell.env exposes session id + cwd.
  const out3: any = { env: {} }
  await hooks["shell.env"]({ sessionID: SESSION, cwd }, out3)
  check(
    "shell.env exposes BRAINSTORM_* vars",
    out3.env.BRAINSTORM_SESSION_ID === SESSION && out3.env.BRAINSTORM_CWD === cwd,
  )

  // 8) deactivate → edit is unblocked again.
  const deact = py("deactivate.py", [])
  check("deactivate.py exits 0", deact.status === 0)
  let threwAfter = false
  try {
    await hooks["tool.execute.before"]({ tool: "edit", sessionID: SESSION }, { args: {} })
  } catch {
    threwAfter = true
  }
  check("edit allowed after /brainstorm-done", !threwAfter)
} finally {
  rmSync(cwd, { recursive: true, force: true })
}

console.log(failures === 0 ? "\nALL OPENCODE SMOKE CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`)
process.exit(failures === 0 ? 0 : 1)
