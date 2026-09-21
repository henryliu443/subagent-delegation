// Tests the REAL plugin hook path: GuardPlugin() -> hooks["tool.execute.before"](...).
// This proves the enforcement decision blocks out-of-contract edit/write/read.
//
// Scope of proof: this exercises the plugin module and its before-hook exactly as
// OpenCode calls it (input {tool,sessionID,callID}, output {args}). It does NOT
// launch an OpenCode agent session. Hook wiring (trigger awaited before execute)
// was verified against the shipped app.asar, not by this test.

import assert from "node:assert/strict"
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"
import GuardPlugin from "../plugin/guard.js"

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, "..")
const workspace = path.join(root, "demo", "parent")

process.env.DELEGATION_CONTRACT = path.join(root, "demo", "contract.json")

const hooks = await GuardPlugin({ directory: workspace, worktree: workspace })
const before = hooks["tool.execute.before"]

async function call(tool, args) {
  try {
    await before({ tool, sessionID: "test", callID: "test" }, { args })
    return { threw: false }
  } catch (e) {
    return { threw: true, message: e.message }
  }
}

const cases = [
  { name: "edit  child-a/test.txt  (in authority.write)", tool: "edit",  args: { filePath: "child-a/test.txt" }, expect: "ALLOW" },
  { name: "write child-a/new.txt   (in authority.write)", tool: "write", args: { filePath: "child-a/new.txt" },  expect: "ALLOW" },
  { name: "read  child-a/test.txt  (in authority.read)",  tool: "read",  args: { filePath: "child-a/test.txt" }, expect: "ALLOW" },
  { name: "edit  child-b/test.txt  (out of authority)",   tool: "edit",  args: { filePath: "child-b/test.txt" }, expect: "DENY"  },
  { name: "write child-b/test.txt  (out of authority)",   tool: "write", args: { filePath: "child-b/test.txt" }, expect: "DENY"  },
  { name: "read  child-b/test.txt  (out of authority)",   tool: "read",  args: { filePath: "child-b/test.txt" }, expect: "DENY"  },
  { name: "read  .git/config       (protected)",          tool: "read",  args: { filePath: ".git/config" },      expect: "DENY"  },
  { name: "write ../escape.txt     (traversal)",          tool: "write", args: { filePath: "../escape.txt" },    expect: "DENY"  },
  { name: "edit  /etc/passwd       (absolute outside)",   tool: "edit",  args: { filePath: "/etc/passwd" },      expect: "DENY"  },
]

let failed = 0
console.log("PLUGIN ENFORCEMENT TEST (tool.execute.before)")
console.log("workspace:", workspace)
console.log("contract :", process.env.DELEGATION_CONTRACT)
console.log("-".repeat(74))
for (const c of cases) {
  const res = await call(c.tool, c.args)
  const actual = res.threw ? "DENY" : "ALLOW"
  const ok = actual === c.expect
  if (!ok) failed++
  console.log(`${ok ? "PASS" : "FAIL"}  ${c.expect.padEnd(5)} got ${actual.padEnd(5)}  ${c.name}`)
  if (!ok) console.log(`        -> ${res.message || "no error thrown"}`)
}
console.log("-".repeat(74))
console.log(failed === 0 ? "OVERALL: PASS" : `OVERALL: FAIL (${failed} failing)`)

// ---------------------------------------------------------------------------
// tool.execute.after (bash) — DETECTION ONLY, cannot prevent what already ran.
// ---------------------------------------------------------------------------
const after = hooks["tool.execute.after"]
const bashInput = { tool: "bash", sessionID: "test", callID: "test" }

async function bashAfter() {
  try {
    await after(bashInput, { args: { command: "true" } })
    return { threw: false }
  } catch (e) {
    return { threw: true, message: e.message }
  }
}

await bashAfter() // establishes baseline

const outside = path.join(workspace, "child-b", "evil.txt")
fs.writeFileSync(outside, "x")
const detectOutside = await bashAfter()
fs.rmSync(outside, { force: true })

const inside = path.join(workspace, "child-a", "ok.txt")
fs.writeFileSync(inside, "x")
const detectInside = await bashAfter()
fs.rmSync(inside, { force: true })

let afterFailed = 0
console.log("POST-TOOL DETECTION TEST (tool.execute.after / bash)")
console.log("-".repeat(74))
{
  const ok = detectOutside.threw === true
  if (!ok) afterFailed++
  console.log(`${ok ? "PASS" : "FAIL"}  detected  bash wrote outside authority (child-b/evil.txt)`)
  if (!ok) console.log("        -> no error thrown")
}
{
  const ok = detectInside.threw === false
  if (!ok) afterFailed++
  console.log(`${ok ? "PASS" : "FAIL"}  allowed   bash wrote inside authority (child-a/ok.txt)`)
  if (!ok) console.log(`        -> ${detectInside.message}`)
}
console.log("-".repeat(74))
console.log(afterFailed === 0 ? "POST-TOOL: PASS" : `POST-TOOL: FAIL (${afterFailed} failing)`)

process.exit(failed === 0 && afterFailed === 0 ? 0 : 1)
