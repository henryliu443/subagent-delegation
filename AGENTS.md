## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current

## subagent delegation & runtime guard

This project defines and enforces the subagent delegation control layer.

Rules:
- Never spawn a subagent without evaluating `SKILL.md` or running `/delegate`.
- Sub-agents must operate under a machine-readable Delegation Contract (`contracts/schema.json`, JSON only).
- Boundary checks are enforced at runtime by the OpenCode plugin `plugin/guard.js` (`tool.execute.before`), which aborts out-of-contract `read`/`edit`/`write`. `bin/subagent-guard` is an offline verifier, not a boundary.
- Architectural changes (deleting parent directory, modifying `.git`, altering repo roots or package topology) are strictly BLOCKED and require human approval.
- An agent cannot self-declare completion; it must pass the Verification Gate (`bin/subagent-guard verify`).
- Do not make the agent smarter. Make the agent more bounded.
