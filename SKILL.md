# Sub-Agent Delegation Skill

> When to hand a task to a sub-agent — and when not to.
> This skill encodes the delegation decision model, the distinction between capability extension and context management, and the layered authority architecture for agent workflows.

---

## Activation

This skill is consulted ONLY when the main agent is about to:

- spawn a sub-agent (task tool, agent delegation, parallel agent branches)
- plan a multi-branch exploration or investigation
- design a workflow, pipeline, or agent configuration that contains delegation

This skill is NOT consulted for:

- direct edits, single-file changes, trivial fixes (e.g. changing two characters)
- reading files, searching, running tests, or any task the main agent does inline

Small tasks never reach the delegation decision point. They are handled inline with zero overhead — there is nothing to bypass.

---

## Purpose

This skill exists to answer one question precisely:

**Under what conditions does delegating a task to a sub-agent produce more value than it costs?**

It is not about implementation. It is about the **economics and boundaries of delegation**.

---

## Core Principle

> **Sub-agent is not a capability extension. It is a runtime context fork.**

A sub-agent is an execution unit that is granted:
- a **local goal**
- a **local context** (isolated from the main agent's context window)
- a **local authority** (a defined scope of action)
- a **return contract** (a structured output, not a conversation)

Whether it runs as a separate process, a separate model instance, or a separate prompt — that is an implementation detail. The architectural meaning is: **context is forked, and only a contracted result flows back.**

---

## The Seven Delegation Values — Distinct and Non-Interchangeable

| Value | What it actually is | When it justifies a sub-agent |
|---|---|---|
| **A. Parallel computation** | Forking N independent explorations simultaneously | Only when each branch requires local judgment, not just mechanical execution |
| **B. Context isolation** | Preventing a task from polluting the main agent's context | When the task is exploratory, high-volume, or likely to produce noise |
| **C. Cognitive specialization** | A role-specific agent (reviewer, tester, researcher) | Only when the specialization requires independent context, authority, or failure domain — otherwise it is a Skill or prompt |
| **D. Independent verification** | A different agent validates output without having produced it | When the cost of undetected error is high AND the verification is truly independent (different evidence, different goal, different prompt) |
| **E. Failure containment** | A failed exploration does not propagate to the main agent | When the task has non-trivial failure probability and the failure would be expensive to unwind |
| **F. Token / cost optimization** | Cheap agent does low-value work, expensive agent makes decisions | Only when the return contract is precise enough that nothing important is lost in summarization |
| **G. Temporal delegation** | A long-running task does not block the main agent | Only when the task requires agent judgment during execution — otherwise it is a job, queue, or CI step |

---

## What Should NOT Be a Sub-Agent

The following are frequently misclassified as sub-agent use cases. They are not.

| Misclassified case | Correct abstraction |
|---|---|
| Mechanical parallelization (run 50 tests) | `script`, `CI`, `parallel tool calls` |
| Deterministic multi-step workflow | `workflow`, `pipeline`, `DAG` |
| Long-running computation | `job`, `queue`, `async task` |
| Simple file search or grep | `tool call` |
| Code formatting or linting | `script`, `hook` |
| Reading many files to answer a question | `main agent` — unless the volume would overflow context |
| A task that needs the same model to "think differently" | `prompt variation`, not a new agent |

**Rule of thumb:** If the task does not require *local judgment under uncertainty*, it does not need an agent. It needs a tool, a script, or a workflow.

---

## The Delegation Decision Model

A multi-factor model, not a single threshold. Each factor is scored, and the composite determines delegation.

### Input Factors

```
task_complexity          : low | medium | high
context_size_if_inline   : tokens that would enter main context if done inline
context_contamination    : low | medium | high  (noise, dead ends, irrelevant detail)
parallelism              : 1 | N independent branches
independence             : coupled | loosely coupled | fully independent
verification_value       : low | medium | high  (cost of undetected error)
latency_tolerance        : blocking | non-blocking
token_cost_asymmetry     : main agent cost vs sub-agent cost
model_capability_gap     : none | moderate | large
failure_probability      : low | medium | high
reversibility            : trivial | moderate | irreversible
task_importance          : low | medium | high | critical
needs_human_approval     : no | yes
```

### Decision Logic

```
DELEGATE when ANY of these are true AND none of the veto conditions apply:

  1. context_contamination is high
     AND context_size_if_inline > 20% of main context window

  2. parallelism >= 2
     AND each branch requires local judgment (not just execution)

  3. verification_value is high
     AND the verifying agent is truly independent
     (different evidence, different goal, or adversarial prompt)

  4. failure_probability is medium or high
     AND the task is exploratory (unknown unknowns)
     AND failure cost is high

  5. task is fully independent
     AND latency_tolerance is non-blocking
     AND token_cost_asymmetry favors delegation

VETO (do not delegate) when ANY of these are true:

  1. task is trivial (mechanical, deterministic, no judgment required)

  2. task requires shared context with the main agent's current reasoning
     (splitting would lose critical state)

  3. delegation_overhead > expected_gain
     where delegation_overhead includes:
       - tokens to spawn and brief the sub-agent
       - latency of the sub-agent run
       - tokens to return and integrate the result
       - coordination cost
       - error surface introduced by the fork

  4. task is irreversible AND task_importance is critical
     AND no independent verification is planned

  5. the task can be done by a script, tool, or workflow
     with equal or better reliability
```

---

## The Return Contract

The most under-engineered part of sub-agent systems.

**Problem:** If the sub-agent returns a full log, it pollutes the main context. If it returns only "success/failure", the main agent loses the reasoning needed for the next decision.

**Solution:** The return contract is a **structured state delta**, not a conversation.

```
ReturnContract:
  status            : success | partial | failure | blocked
  summary           : 1-3 sentences, decision-grade
  key_findings      : list of facts that change the main agent's next action
  artifacts         : file paths, diffs, test results, URLs
  errors            : structured error objects, not stack traces
  context_delta     : what the main agent should now believe that it did not before
  open_questions    : anything unresolved that the main agent must decide
```

**Anti-pattern:** Returning a narrative of everything the sub-agent did. The main agent does not need the journey. It needs the destination and any obstacles discovered.

---

## The Delegation Contract

A sub-agent is not bounded by polite instructions. It is bounded by a **machine-readable Delegation Contract**.

> **Delegation Contract is the sub-agent's authority boundary, not a prompt suggestion.**

### Contract Specification (JSON is the only runtime format)

```json
{
  "delegation": {
    "id": "delegate-001",
    "goal": "Review authentication implementation and add negative tests",
    "context": {
      "include": ["src/auth/**", "tests/auth/**"],
      "exclude": [".git/**", "secrets/**", "**/.env*"]
    },
    "authority": {
      "read": ["src/auth/**", "tests/auth/**"],
      "write": ["tests/auth/**"],
      "execute": ["pytest tests/auth", "python3 -m unittest"],
      "deny": ["git push*", "git reset --hard*", "git clean*", "rm -rf*", "delete", ".git/**"]
    },
    "return": { "format": "structured", "required": ["status", "findings", "evidence", "uncertainty"] },
    "verification": { "required": true, "commands": ["pytest tests/auth"] },
    "budget": { "max_tokens": 20000, "max_duration_seconds": 300 }
  }
}
```

> YAML is documentation only. Runtime parsing is JSON only.

---

## The Runtime Guard (how it is actually enforced)

Agents can decide *whether delegation is needed*, but the agent cannot decide what permissions
delegation gets, and cannot bypass the runtime enforcement.

```text
Main Agent
    ↓
Delegation Decision (SKILL.md / /delegate)          [DOCUMENTATION ONLY]
    ↓
Delegation Contract (.opencode/delegation-contract.json)
    ↓
OpenCode runtime
    ├─ native permission                            [RUNTIME ENFORCED]
    └─ plugin guard.js  tool.execute.before (throw) [RUNTIME ENFORCED]
    ↓
Sub-agent Execution
```

`bin/subagent-guard` is an **offline verifier**, not the boundary. It only runs when invoked.
Do not describe it as enforcement.

### Enforcement levels

- **RUNTIME ENFORCED** — OpenCode `permission` and the plugin `tool.execute.before` hook
  (verified: the hook is awaited before the tool executes, so throwing aborts the call).
- **PARTIALLY ENFORCED** — `bash` prefix rules and post-tool detection.
- **DOCUMENTATION ONLY** — everything in this file, `AGENTS.md`, and `/delegate` output.

### Operation Taxonomy

| Category | Policy | Description / Examples |
|---|---|---|
| **ALLOW** | Automatic | Path within `authority.read` / `authority.write`; not excluded, not denied, not protected. |
| **ASK** | Human Approval Required | Native permission `ask` (external directories, non-allowlisted `bash`). |
| **DENY** | Strictly Blocked | Path traversal (`..`), workspace escape, `.git`, `context.exclude`, `authority.deny`, or any path outside the relevant authority list. Enforced by the plugin hook. |

---

## Architecture Change Gate

A major hazard in autonomous coding agents is runaway blast radius: when a localized task fails (such as a dependency resolution error or test failure), the model attempts to fix it by altering the architecture of the repository.

> **Agent rule:** An agent is NEVER permitted to automatically alter repository architecture because of a localized failure.

### Intercepted Operations

- Repository root or workspace root alterations
- Package root changes (modifying/deleting `pyproject.toml`, `package.json`, `Cargo.toml`, etc.)
- Parent directory deletion or modification (`rm -rf ..`, `delete parent/`)
- Sibling project modifications
- Direct tampering with `.git` internals
- Restructuring top-level directory layout or package hierarchy

When detected by the Architecture Gate:

```text
BLOCKED

Architectural change detected.

Reason:
<reason>

Requested:
<operation>

Required:
Human approval
```

The model **cannot** self-approve or explain away an architectural change gate block.

---

## Verification Gate

An agent cannot unilaterally announce `DONE`. Completion is a verified state transition:

```text
EXECUTE
   ↓
VERIFY
   ↓
PASS
   ↓
DONE
```

### Verification Checks

1. **Working Tree Boundary Check:** Evaluates `git status --porcelain` to verify that no files outside `authority.write` were touched, and no protected or architectural files were modified.
2. **Deterministic Commands:** Executes verification commands (`pytest`, `npm test`, linter, build) defined in `contract.verification.commands`.

If verification fails:

```text
COMPLETION REJECTED

Reason:
<verification failure diagnostics>
```

Failure diagnostics are returned to the agent to remediate within its authority boundaries.

---

## The Watchdog

A lightweight, non-intrusive monitor designed to detect runaway, stalled, or anomalous sub-agents without complex daemons:

```text
Periodically checks (~20s interval or step evaluation):
- Current working directory (must remain within workspace boundary)
- Git status (checks for unauthorized or protected file modifications)
- Changed files (compares against contract write globs)
- Last action timestamp (flags inactivity or hung subprocesses)
- Task state (flags repeated failures)
```

If a violation is detected:

```text
PAUSE / BLOCK

Watchdog violation detected:
<violation details>
```

**Guard Principles:**
- No auto-recovery
- No auto-restart
- No unauthorized self-repair
- Control is immediately returned to the main agent / human

---

## Separation of Concerns: Instructions vs. Runtime Policy

```text
AGENTS.md / SKILL.md
  → Instructions: Tells the agent what it SHOULD do.

OpenCode permission + plugin guard.js (tool.execute.before) / OS / Git
  → Runtime Policy: Determines what it is ALLOWED to do.
```

- **DOCUMENTATION ONLY:** prompt markdown that relies on LLM instruction-following
  (`SKILL.md`, `AGENTS.md`, `/delegate`, and the `subagent-guard` CLI when not invoked).
- **RUNTIME ENFORCED:** OpenCode `permission` and the plugin `tool.execute.before` hook,
  plus OS/filesystem boundaries.
- **PARTIALLY ENFORCED:** `bash` prefix rules and post-tool detection.

> **Core Mandate:** Do not make the agent smarter. Make the agent more bounded.

---

---

## Architecture: Who Owns the Delegation Decision?

Three candidate architectures, and why none is sufficient alone.

### Architecture A: Main Agent Decides

```
Human → Main Agent → Sub-agent
```

- **Pro:** Flexible, context-aware, can adapt to novel situations
- **Con:** Sub-agent proliferation; agent spawns sub-agents to appear thorough; no audit trail; hard to budget

### Architecture B: Workflow Defines Rules

```
Human → Workflow/Skill → Main Agent → Sub-agent
```

- **Pro:** Predictable, auditable, budgetable, testable
- **Con:** Rigid; cannot handle novel task shapes; rules become stale; over-constrains the agent

### Architecture C: System Dynamically Decides

```
Human → Agent System → Agent / Sub-agent / Tools
```

- **Pro:** Can optimize globally; can learn from outcomes; can balance load
- **Con:** Opaque; hard to debug; hard to build trust; system may optimize for metrics that do not match human intent

### Recommended: Layered Authority

```
Layer 1 — Human
  Defines: risk boundaries, budget, non-delegable categories, approval gates

Layer 2 — Workflow / Skill
  Defines: delegable task categories, return contract templates, parallelism limits

Layer 3 — Main Agent
  Decides: within the boundaries set by Layer 1 and 2, whether to delegate this specific instance

Layer 4 — System
  Provides: audit log, rollback, cost tracking, failure containment
```

**Key insight:** The delegation decision is not a single point of authority. It is a **nested set of constraints**. The human sets the outer boundary. The workflow sets the category. The agent decides within the category. The system enforces the contract.

---

## The Bootstrap Paradox

> *Who can decide whether a task should be delegated before knowing what the task will unfold into?*

To decide whether to isolate context, the main agent must first understand the task. But understanding the task consumes or pollutes the very context it would isolate. Sending a "scout" sub-agent is itself a delegation. And the scout's report still enters the main context.

**Current best answer:**

1. **Use metadata, not payload.** The main agent does not need to read every file to decide. It can use file trees, ASTs, function signatures, and the user's high-level intent as a map. The decision to delegate is made on **structural metadata**, not on full content.

2. **Fast-fail with structured error returns.** If a sub-agent hits a boundary, it returns a structured error (cost exceeded, dependency missing, scope unclear), not a narrative of its confusion. The main agent receives a status code and a decision point, not a pollution stream.

3. **Accept that delegation is a prior bet.** All delegation thresholds are bets made under uncertainty. The system should be designed to make bets cheap to place, cheap to fold, and easy to audit.

---

## Anti-Patterns

| Anti-pattern | Why it fails |
|---|---|
| "Complex task → sub-agent" | Complexity is not the variable. Context contamination, independence, and verification value are. |
| "One agent per role" (tester, reviewer, researcher) | Roles are prompt/skill specializations. They only need to be sub-agents if they need independent context, authority, or failure domain. |
| "Sub-agent for everything" | More agents = more coordination cost, more failure surface, more token spend, more latency. |
| "Return everything the sub-agent found" | Pollutes main context. The return contract must be selective. |
| "Let the model decide autonomously" | Leads to sub-agent proliferation. Agents spawn sub-agents to appear thorough, not to solve problems. |
| "Write all rules in the workflow" | Cannot handle novel tasks. Rules become stale. Over-constrains the agent. |

---

## Open Questions

These are unresolved. Do not treat them as settled.

1. **Can a non-textual state compression protocol exist?** Can a sub-agent inject its cognitive delta (discovered constraints, hidden API limits, dependency conflicts) directly into a shared state graph or external memory, without going through natural language?

2. **Is there a runtime context fork mechanism** where the *decision to delegate* and the *execution* happen in different contexts, so that the decision itself does not consume the context it is trying to protect?

3. **How do different agent frameworks (Claude, Kimi, OpenCode) differ in their delegation philosophy?** — Insufficient public data. Do not assume. Mark as unknown.

---

## Practical Heuristics

For day-to-day use, when the full decision model is too heavy:

```
Ask these four questions in order:

1. Can a script or tool do this?          → YES → do not delegate
2. Will this pollute my context?          → YES → delegate
3. Does this need independent eyes?       → YES → delegate (with adversarial prompt)
4. Can this run in parallel with my work? → YES → delegate (with return contract)

If all four are NO → do it in the main agent.
```

---

## Summary

Sub-agent delegation is not about giving the agent "another brain."

It is about giving a task **its own context, its own failure boundary, and its own verification boundary** — when the economics justify the fork.

The decision is not "complex → delegate." It is:

> **Delegate when the cost of doing the task inline (context pollution, error propagation, blocking, undetected failure) exceeds the cost of the fork (spawn overhead, coordination, return integration, latency).**

And the decision is not made by one entity. It is made by a **layered authority**: human sets boundaries, workflow sets categories, agent decides within them, system enforces contracts.
