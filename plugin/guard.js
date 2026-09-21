// OpenCode plugin: enforce a Delegation Contract at runtime.
//
// Enforcement point: "tool.execute.before" is awaited by OpenCode BEFORE the tool
// implementation runs (verified in app.asar). Throwing aborts the tool call.
//
// This file exports ONLY `default` (a Plugin factory). OpenCode treats any named
// function export as a plugin, so keep helpers module-private.
//
// Runtime contract format: JSON only.
// Contract discovery order:
//   1. $DELEGATION_CONTRACT (absolute path)
//   2. <worktree>/.opencode/delegation-contract.json
// If no contract is found, the plugin is inert (fail-open to normal OpenCode rules).

import fs from "node:fs"
import path from "node:path"
import { execFileSync } from "node:child_process"

const PATH_TOOLS = { read: "read", edit: "write", write: "write", patch: "write" }

function norm(p) {
  return String(p).replace(/\\/g, "/").replace(/^\.\//, "")
}

function globToRegExp(pattern) {
  let re = "^"
  for (let i = 0; i < pattern.length; i++) {
    const c = pattern[i]
    if (c === "*") {
      if (pattern[i + 1] === "*") {
        i++
        if (pattern[i + 1] === "/") {
          i++
          re += "(?:.*/)?"
        } else {
          re += ".*"
        }
      } else {
        re += "[^/]*"
      }
    } else if (c === "?") {
      re += "[^/]"
    } else {
      re += c.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
    }
  }
  return new RegExp(re + "$")
}

function matchesAny(rel, patterns) {
  for (const p of patterns || []) {
    const clean = norm(p)
    if (clean.endsWith("/**")) {
      const prefix = clean.slice(0, -3).replace(/\/$/, "")
      if (rel === prefix || rel.startsWith(prefix + "/")) return p
    }
    try {
      if (globToRegExp(clean).test(rel)) return p
    } catch {}
  }
  return null
}

function loadContract(root) {
  const candidates = []
  if (process.env.DELEGATION_CONTRACT) candidates.push(process.env.DELEGATION_CONTRACT)
  candidates.push(path.join(root, ".opencode", "delegation-contract.json"))
  for (const c of candidates) {
    try {
      if (c && fs.existsSync(c)) return JSON.parse(fs.readFileSync(c, "utf8"))
    } catch {}
  }
  return null
}

// Pure decision function. Returns { allow, reason, rule }.
function evaluate(contract, tool, args, workspaceRoot) {
  if (!contract) return { allow: true, reason: "no contract", rule: null }
  const d = contract.delegation || contract
  const authority = d.authority || {}
  const context = d.context || {}
  const kind = PATH_TOOLS[tool]
  if (!kind) return { allow: true, reason: "tool not path-scoped", rule: null }

  const raw = args && (args.filePath || args.path || args.file_path)
  if (typeof raw !== "string" || raw.length === 0) {
    return { allow: false, reason: `${tool} called without a resolvable file path`, rule: null }
  }
  if (norm(raw).split("/").includes("..")) {
    return { allow: false, reason: `path traversal '..' in '${raw}'`, rule: ".." }
  }

  const abs = path.isAbsolute(raw)
    ? path.normalize(raw)
    : path.normalize(path.join(workspaceRoot, raw))
  const rel = norm(path.relative(workspaceRoot, abs))
  if (rel === ".." || rel.startsWith("../")) {
    return { allow: false, reason: `path escapes workspace: '${raw}'`, rule: "boundary" }
  }
  if (rel.split("/").includes(".git")) {
    return { allow: false, reason: ".git internal directory is protected", rule: ".git/**" }
  }

  const excl = matchesAny(rel, context.exclude)
  if (excl) return { allow: false, reason: `excluded by context.exclude '${excl}'`, rule: excl }

  const denied = matchesAny(rel, authority.deny)
  if (denied) return { allow: false, reason: `denied by authority.deny '${denied}'`, rule: denied }

  const allowList = kind === "read" ? authority.read : authority.write
  const ok = matchesAny(rel, allowList)
  if (ok) return { allow: true, reason: `allowed by '${ok}'`, rule: ok }
  return {
    allow: false,
    reason: `'${rel}' is not in authority.${kind} [${(allowList || []).join(", ")}]`,
    rule: null,
  }
}

function gitPrefix(workspaceRoot) {
  try {
    return execFileSync("git", ["rev-parse", "--show-prefix"], {
      cwd: workspaceRoot,
      encoding: "utf8",
    }).trim()
  } catch {
    return ""
  }
}

function changedFiles(workspaceRoot) {
  try {
    const prefix = gitPrefix(workspaceRoot)
    const out = execFileSync("git", ["status", "--porcelain", "-uall"], {
      cwd: workspaceRoot,
      encoding: "utf8",
    })
    return out
      .split("\n")
      .filter(Boolean)
      .map((l) => {
        let f = l.slice(3).trim()
        if (f.includes(" -> ")) f = f.split(" -> ")[1].trim()
        if (prefix && f.startsWith(prefix)) f = f.slice(prefix.length)
        return f
      })
  } catch {
    return []
  }
}

export default async ({ directory, worktree }) => {
  const root = worktree || directory
  let baseline = null

  return {
    "tool.execute.before": async (input, output) => {
      const contract = loadContract(root)
      if (!contract) return
      const res = evaluate(contract, input.tool, output.args, root)
      if (!res.allow) {
        throw new Error(`DELEGATION CONTRACT DENY [${input.tool}]: ${res.reason}`)
      }
    },

    "tool.execute.after": async (input) => {
      const contract = loadContract(root)
      if (!contract) return
      // Only bash needs post-hoc inspection: its target files cannot be known in advance.
      if (input.tool !== "bash") return
      const d = contract.delegation || contract
      const write = (d.authority && d.authority.write) || []
      if (baseline === null) baseline = new Set(changedFiles(root))
      // DETECTION ONLY. bash has already executed; this cannot prevent the change.
      const offenders = changedFiles(root).filter((f) => {
        const rel = norm(f)
        if (baseline.has(f)) return false
        if (rel.split("/").includes(".git")) return true
        return !matchesAny(rel, write)
      })
      if (offenders.length) {
        throw new Error(
          `DELEGATION CONTRACT DETECTION (post-execution, NOT prevention): bash changed files outside authority.write: ${offenders.join(", ")}`
        )
      }
    },
  }
}
