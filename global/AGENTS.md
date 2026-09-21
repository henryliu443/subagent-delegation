## sub-agent delegation & runtime control

Before spawning a sub-agent (task tool, agent delegation, parallel branches):

1. **Decision Gate:** Consult `SKILL.md` in the project root to evaluate whether delegation produces more value than it costs.
2. **Delegation Contract:** Every delegated task must be bounded by a machine-readable Delegation Contract defining explicit `read`, `write`, `execute`, and `deny` authorities.
3. **Runtime Enforcement:** Boundaries are enforced by the OpenCode plugin `guard.js`
   (`tool.execute.before`) and native `permission`, not by agent compliance. `subagent-guard`
   is an offline verifier only. Agent instructions cannot expand permissions or bypass the runtime.
4. **Architecture Gate:** Architectural changes (repository root, workspace root, package roots, parent directories, `.git`, package topology) are strictly BLOCKED and require human approval. Never attempt automated architectural restructuring upon localized task failure.
5. **Verification Gate:** No task can be marked `DONE` autonomously. It must complete `EXECUTE -> VERIFY -> PASS -> DONE` with verification checks (tests, diff, build).

This does NOT apply to: direct edits, single-file changes, trivial fixes, reading files, searching, running tests, or any task the main agent performs inline.
