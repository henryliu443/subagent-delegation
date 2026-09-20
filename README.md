# Sub-Agent Delegation Skill

**When should a main agent hand a task to a sub-agent — and when should it just do the work itself?**

**English** | [中文](README.zh-CN.md)

[![Made for OpenCode](https://img.shields.io/badge/made%20for-OpenCode-000000?style=flat-square)](https://opencode.ai)
[![Type: Agent Skill](https://img.shields.io/badge/type-agent%20skill-6f42c1?style=flat-square)](#)
[![Status: Open Question](https://img.shields.io/badge/status-open%20question-orange?style=flat-square)](#open-questions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

> A delegation decision framework for coding agents.
> Not "more agents = more advanced." This is about the **economics and boundaries of delegation.**

---

## What This Is

This repo is a small, installable skill for OpenCode (and adaptable to other coding agents). It answers one question precisely:

> **Under what conditions does delegating a task to a sub-agent produce more value than it costs?**

It is **not** a sub-agent implementation. It is a decision model: a structured way to decide whether a task should be forked to a sub-agent, kept inline, or split.

### The core principle

> **A sub-agent is not a capability extension. It is a runtime context fork.**

A sub-agent is an execution unit granted:
- a **local goal**
- a **local context** (isolated from the main agent's window)
- a **local authority** (a defined scope of action)
- a **return contract** (a structured result, not a conversation)

Whether it runs as a separate process, model, or prompt is an implementation detail. The architectural meaning is: **context is forked, and only a contracted result flows back.**

---

## What's Inside

| File | Purpose |
|---|---|
| `SKILL.md` | The delegation decision model — 7 delegation values, 13 factors, 5 triggers, 5 veto conditions, return contract, layered authority architecture |
| `global/AGENTS.md` | Global hook installed to `~/AGENTS.md` — makes the agent consult `SKILL.md` before spawning sub-agents |
| `global/command/delegate.md` | Global `/delegate` slash command for OpenCode |
| `install.sh` | One-command installer that places the global hook and command |
| `AGENTS.md` | Project-level agent config |

---

## Install

```bash
git clone https://github.com/henryliu443/subagent-delegation.git
cd subagent-delegation
./install.sh
```

`install.sh` does two things:

1. Copies `global/AGENTS.md` → `~/AGENTS.md` (global delegation hook)
2. Copies `global/command/delegate.md` → `~/.config/opencode/command/delegate.md` (global `/delegate` command)

After that, open OpenCode in **any** project. The hook is active.

> **API key note:** This repo contains no secrets. Provider configuration (`~/.config/opencode/opencode.jsonc`) stays local and is never committed.

---

## Usage

### Automatic

Once installed, the global hook tells the agent to consult `SKILL.md` before spawning any sub-agent. Trivial tasks (direct edits, single-file changes, searches, tests) never reach the delegation decision point — they bypass automatically with zero overhead.

### Manual

Use the `/delegate` command to run the decision model on any task or plan:

```
/delegate explore all API endpoints in this codebase and map dependencies
```

Returns:

```
RECOMMENDATION: DELEGATE | INLINE | HYBRID
Confidence: high | medium | low
Reasoning: <1-3 sentences>
Sub-agent type: <parallel | context-branch | reviewer | verifier | sandbox>
Return contract: <what flows back>
Risk: <what could go wrong>
```

---

## The Decision Model (Summary)

**Delegate when any trigger is true and no veto applies:**

1. Context contamination is high and the task would consume >20% of the main context
2. Two or more branches each require local judgment
3. Verification value is high and the verifier is truly independent
4. Failure probability is non-trivial, the task is exploratory, and failure is costly
5. The task is fully independent, non-blocking, and cheaper to delegate

**Veto (do not delegate) when any is true:**

1. The task is trivial (mechanical, deterministic, no judgment)
2. The task requires shared context with the main agent's current reasoning
3. Delegation overhead > expected gain
4. The task is irreversible and critical, with no independent verification
5. A script, tool, or workflow can do it with equal or better reliability

See `SKILL.md` for the full 13-factor model, return contract, and layered authority architecture.

---

## What Should NOT Be a Sub-Agent

| Misclassified case | Correct abstraction |
|---|---|
| Mechanical parallelization | `script`, `CI`, parallel tool calls |
| Deterministic multi-step workflow | `workflow`, pipeline, DAG |
| Long-running computation | `job`, queue, async task |
| Simple file search | `tool call` |
| Formatting or linting | `script`, hook |
| "Make the model think differently" | `prompt variation`, not a new agent |

> **Rule of thumb:** If a task does not require *local judgment under uncertainty*, it does not need an agent. It needs a tool.

---

## Architecture: Who Owns the Delegation Decision?

Not a single point of authority — a **nested set of constraints**:

```
Layer 1 — Human     : risk boundaries, budget, non-delegable categories, approval gates
Layer 2 — Workflow  : delegable categories, return contract templates, parallelism limits
Layer 3 — Agent     : decides within those boundaries whether to delegate this instance
Layer 4 — System    : audit log, rollback, cost tracking, failure containment
```

Writing all rules into the workflow is rigid. Giving the model full autonomy causes sub-agent proliferation. **Layering is the realistic answer.**

---

## Open Questions

This repo intentionally keeps its central problem open:

1. **Can a non-textual state compression protocol exist?** Can a sub-agent inject its cognitive delta directly into a shared state graph or memory, bypassing natural-language reporting?
2. **Is there a runtime context fork where the decision to delegate and the execution happen in different contexts?** Or are all delegation thresholds prior bets under uncertainty?
3. **How do Claude, Kimi, and OpenCode differ in delegation philosophy?** Insufficient public data — marked as unknown, not assumed.

---

## License

MIT
