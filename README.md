# Sub-Agent Delegation Control Layer

**When should a main agent hand a task to a sub-agent — and how is the sub-agent actually bounded at runtime?**

**English** | [中文](README.zh-CN.md)

[![Made for OpenCode](https://img.shields.io/badge/made%20for-OpenCode-000000?style=flat-square)](https://opencode.ai)
[![Type: Delegation Control Layer](https://img.shields.io/badge/type-control%20layer-6f42c1?style=flat-square)](#)
[![Runtime format: JSON](https://img.shields.io/badge/contract-JSON%20only-success?style=flat-square)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

> A delegation decision framework and a runtime enforcement layer for coding agents.
> Not "more agents = more advanced." This is about **who is allowed to do what, enforced by the runtime.**

---

## Core Thesis

> **A sub-agent is not a capability extension. It is a runtime context fork.**
> **An agent may decide *whether* to delegate. It does not get to decide *what permissions* delegation receives.**

```text
Instructions tell the agent what it SHOULD do.
Runtime policy determines what it is ALLOWED to do.
```

---

## Enforcement Model (read this first)

There are three distinct levels in this repo. They are not interchangeable.

| Level | Meaning | Where it lives |
|---|---|---|
| **RUNTIME ENFORCED** | Violation aborts the operation in the OpenCode process, before or regardless of model intent. | OpenCode `permission` config, plugin `tool.execute.before` |
| **PARTIALLY ENFORCED** | Only some cases are caught; bypass is possible. | `bash` command-prefix rules, post-tool detection |
| **DOCUMENTATION ONLY** | The model is *asked* to comply. Nothing blocks it. | `SKILL.md`, `AGENTS.md`, `/delegate` prompt |

### Actual execution chain

```text
Agent (LLM emits a tool call)
   ↓
OpenCode runtime
   ├─ permission check (config.permission / agent frontmatter)   [native, RUNTIME ENFORCED]
   ├─ plugin hook  tool.execute.before  (throw = abort)          [native, RUNTIME ENFORCED]
   ↓
Tool implementation (bash / edit / write / read / task / ...)
   ├─ plugin hook  tool.execute.after   (detect only)            [native, DETECTION ONLY]
   ↓
OS / filesystem / shell   ← the only hard boundary once bash runs
```

`bin/subagent-guard` (Python) is **not** on this chain. It is an offline verifier.
Anything it "enforces" only counts when the agent voluntarily calls it — that is DOCUMENTATION ONLY.

---

## What's Inside

| Path | Purpose | Level |
|---|---|---|
| `plugin/guard.js` | OpenCode plugin. Enforces the contract at `tool.execute.before`; aborts out-of-contract `read`/`edit`/`write`. | **RUNTIME ENFORCED** |
| `contracts/opencode.permission.example.jsonc` | Native `permission` baseline (external dirs, secrets, destructive prefixes). | **RUNTIME ENFORCED** if merged |
| `contracts/agent.example.md` | Native per-subagent `permission` frontmatter. | **RUNTIME ENFORCED** if used |
| `contracts/schema.json`, `contracts/example-contract.json` | Delegation Contract schema + example. JSON is the only runtime format. | — |
| `test/guard-plugin.test.mjs` | Tests the real plugin hook: in-scope allow, out-of-scope/traversal/protected deny, bash detection. | — |
| `guard/`, `bin/subagent-guard` | Offline verifier / policy calculator. Not a boundary. | DOCUMENTATION ONLY |
| `SKILL.md` | Delegation decision model (7 values, 13 factors, 5 triggers, 5 vetoes, layered authority). | DOCUMENTATION ONLY |
| `global/AGENTS.md`, `global/command/delegate.md` | Global hook + `/delegate` prompt. | DOCUMENTATION ONLY |
| `demo/` | Boundary demo (6 cases) via the offline verifier. | — |
| `install.sh` | Local-only installer (hook, command, plugin, verifier symlink). | — |

---

## Install (local, offline, no secrets touched)

```bash
git clone https://github.com/henryliu443/subagent-delegation.git
cd subagent-delegation
./install.sh
```

This places the plugin at `~/.config/opencode/plugins/guard.js`. OpenCode auto-loads it.
**The plugin is inert until a contract exists**, so it does not affect unrelated projects.

Activate enforcement per project by either:

```bash
# option A: per-project contract
mkdir -p .opencode
cp /path/to/example-contract.json .opencode/delegation-contract.json

# option B: explicit path
export DELEGATION_CONTRACT=/abs/path/contract.json
```

---

## The Delegation Contract (JSON — the only runtime format)

```json
{
  "delegation": {
    "id": "delegate-001",
    "goal": "Audit JWT expiration handling and add negative tests",
    "context": {
      "include": ["src/auth/**", "tests/auth/**"],
      "exclude": [".git/**", "secrets/**", "**/.env*"]
    },
    "authority": {
      "read": ["src/auth/**", "tests/auth/**"],
      "write": ["tests/auth/**"],
      "execute": ["pytest tests/auth"],
      "deny": ["git push*", "git reset --hard*", "git clean*", "rm -rf*", "delete", ".git/**"]
    },
    "return": { "format": "structured", "required": ["status", "findings", "evidence", "uncertainty"] },
    "verification": { "required": true, "commands": ["pytest tests/auth"] },
    "budget": { "max_tokens": 20000, "max_duration_seconds": 300 }
  }
}
```

> YAML may appear in documentation for readability, but it is **never parsed at runtime**.
> Runtime parsing is JSON only.

---

## How the plugin enforces

At `tool.execute.before` (verified in the shipped `app.asar`: the hook is awaited *before*
`tool.execute`), for `read` / `edit` / `write` / `patch`:

1. Resolve `args.filePath` against the workspace root.
2. **DENY** if the path contains `..`.
3. **DENY** if it resolves outside the workspace root.
4. **DENY** if it touches `.git`.
5. **DENY** if it matches `context.exclude` or `authority.deny`.
6. **DENY** if it does not match `authority.read` (for read) or `authority.write` (for edit/write).
7. Otherwise allow.

On any DENY the hook throws, and the tool call does not run.

`tool.execute.after` runs only for `bash` and is **DETECTION ONLY** — it reports changed files
outside `authority.write`. It cannot prevent what bash already did.

---

## Native OpenCode permission

Use native `permission` for everything it can express statically. See
`contracts/opencode.permission.example.jsonc` (baseline) and `contracts/agent.example.md`
(per-subagent frontmatter). Key limits:

- `external_directory` — paths outside the workspace.
- `read` — secret file patterns.
- `bash` — command-prefix rules. **PARTIALLY ENFORCED**: prefixes are string matching and are bypassable via `python3 -c`, variables, base64, etc.

---

## Verify

```bash
node test/guard-plugin.test.mjs   # plugin enforcement (before + after)
./demo/run_demo.sh                # offline verifier boundary demo
```

---

## Enforcement Matrix (accurate)

| Mechanism | Level | Backing |
|---|---|---|
| `read`/`edit`/`write` path boundary from contract | **RUNTIME ENFORCED** | plugin `tool.execute.before` (throws before execute) |
| `..` traversal / workspace escape | **RUNTIME ENFORCED** | plugin `tool.execute.before` |
| `.git` protection | **RUNTIME ENFORCED** | plugin `tool.execute.before` |
| `external_directory` | **RUNTIME ENFORCED** | native `permission` |
| Per-subagent `edit: deny` etc. | **RUNTIME ENFORCED** | native agent frontmatter |
| `bash` destructive commands | **PARTIALLY ENFORCED** | native `permission.bash` prefix rules + plugin after-hook detection |
| `bash` filesystem effects | **PARTIALLY ENFORCED** | after-hook detects; cannot prevent |
| Post-tool changed-file audit | **DETECTION ONLY** | plugin `tool.execute.after` |
| `bin/subagent-guard` CLI | **DOCUMENTATION ONLY** | only runs if invoked |
| Delegation decision / `/delegate` output | **DOCUMENTATION ONLY** | prompt |

---

## Threat model: can the agent disable the guard?

Audited against the installed layout. "Agent" = a subagent holding `bash` + `edit`/`write`.

| Attack | Via `edit`/`write` tool | Via `bash` |
|---|---|---|
| Overwrite `~/.config/opencode/plugins/guard.js` | **BLOCKED** (path escapes workspace) | **BYPASS** (proven: bash rewrote the file) |
| Edit `~/.config/opencode/opencode.jsonc` | **BLOCKED** | **BYPASS** |
| Edit the contract `<ws>/.opencode/delegation-contract.json` | **BLOCKED** | **BYPASS** |
| Widen the contract, then act | BLOCKED, then re-read | **BYPASS** (contract is re-read every call) |
| `export DELEGATION_CONTRACT=...` in a child shell | — | **BLOCKED** (child env does not reach the OpenCode process) |
| Persist `export` into `~/.zshrc` | — | **BYPASS on next restart** |
| Drop a new plugin into `.opencode/plugins/` | — | **UNVERIFIED** (loading requires restart) |

The guard is **not** a trust boundary against an agent that holds `bash`:
the plugin, the native config, and the contract are all ordinary user-writable files,
and post-tool detection cannot see them (they are outside the git repo).

---

## Known bypass paths (honest)

1. **`bash` is the hole.** The plugin sees `bash` as an opaque string. A subagent with `bash`
   can overwrite `guard.js`, the OpenCode config, or the contract. This was reproduced, not inferred.
   True containment needs an OS sandbox (container/`bwrap`/restricted user) or `bash` restricted
   to an allowlisted prefix set.
2. **The contract is re-read on every call.** It is a mutable file; widening it changes policy
   immediately for subsequent tool calls. The guard does not pin or hash its own contract.
3. **Post-tool detection is repo-scoped.** `git status` cannot see writes outside the repository,
   so tampering with the plugin or global config is invisible to the after-hook.
4. **Contract scope is process-wide.** No per-session identity at the hook, so a present contract
   applies to all sessions in that OpenCode process. Per-subagent scoping must come from native
   agent frontmatter.
5. **`DELEGATION_CONTRACT` is process env.** A child shell cannot change it at runtime, but
   persisting it into a shell profile and restarting OpenCode would take effect.

**Conclusion:** the path boundary is real for the `read`/`edit`/`write` tools. It is **not** a
boundary against an agent that can run arbitrary `bash`. Closing that requires OS-level isolation;
it cannot be closed inside the same process with the same filesystem permissions.

---

## License

MIT
