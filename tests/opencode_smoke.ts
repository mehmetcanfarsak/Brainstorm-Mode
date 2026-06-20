/**
 * OpenCode plugin integration smoke test.
 *
 * Loads the real plugin (agents/opencode/plugin/brainstorm-mode.ts) and drives
 * each hook against the real Python core — no LLM required. Verifies the
 * plugin↔python boundary end to end: activate → block edit / allow bash /
 * inject reminder / re-anchor on compaction / expose env → deactivate → unblock,
 * plus the v1.1.0 modes (academic venue policy, mid-session --add-venues,
 * actionable) flowing through chat.message.
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

  // 2) chat.message injects the reminder by MUTATING the existing text part.
  //    (Pushing a new bare part corrupts OpenCode's provider request — verified
  //    against the live gateway — so we must not add parts, only edit text.)
  const userPart: any = { type: "text", text: "let's brainstorm", id: "prt_x" }
  const out1: any = { parts: [userPart] }
  await hooks["chat.message"]({ sessionID: SESSION }, out1)
  check("chat.message does not add parts", out1.parts.length === 1)
  check(
    "chat.message prepends reminder into existing text part",
    out1.parts[0].text.includes("BRAINSTORM MODE ACTIVE") &&
      out1.parts[0].text.includes("let's brainstorm"),
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

  // 9) academic mode: the venue policy flows through chat.message end to end.
  const ACAD = "smoke-academic"
  const a = py("activate.py", ["--mode", "academic", "--venues", "NeurIPS, ICML", "robustness"],
               { BRAINSTORM_SESSION_ID: ACAD })
  check("academic activate exits 0", a.status === 0)
  const oa: any = { parts: [{ type: "text", text: "go", id: "p" }] }
  await hooks["chat.message"]({ sessionID: ACAD }, oa)
  const at: string = oa.parts[0].text
  check(
    "academic reminder carries venue policy",
    at.includes("(academic)") && at.includes("allowed venues: NeurIPS, ICML") && at.includes("peer-reviewed"),
  )
  check(
    "academic reminder carries citation-honesty + pacing",
    at.includes("CITATION HONESTY") && at.includes("ONE question"),
  )

  // 10) mid-session --add-venues is reflected on the next chat.message.
  py("activate.py", ["--add-venues", "XYZ Conf"], { BRAINSTORM_SESSION_ID: ACAD })
  const oa2: any = { parts: [{ type: "text", text: "go", id: "p" }] }
  await hooks["chat.message"]({ sessionID: ACAD }, oa2)
  check("mid-session --add-venues reflected in reminder", oa2.parts[0].text.includes("XYZ Conf"))

  // 11) actionable mode reminder flows through too.
  const ACT = "smoke-actionable"
  py("activate.py", ["--mode", "actionable", "ship the newsletter"], { BRAINSTORM_SESSION_ID: ACT })
  const ob: any = { parts: [{ type: "text", text: "go", id: "p" }] }
  await hooks["chat.message"]({ sessionID: ACT }, ob)
  check("actionable reminder injected", ob.parts[0].text.includes("(actionable)"))
} finally {
  rmSync(cwd, { recursive: true, force: true })
}

console.log(failures === 0 ? "\nALL OPENCODE SMOKE CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`)
process.exit(failures === 0 ? 0 : 1)
