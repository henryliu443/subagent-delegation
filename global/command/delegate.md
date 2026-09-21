Run the Sub-Agent Delegation decision model on the following task or plan.

Read `SKILL.md` in the project root first. Then:

1. Identify the task or plan provided by the user.
2. Evaluate it against the 13 input factors (complexity, context_size, context_contamination, parallelism, independence, verification_value, latency, token_cost, model_capability_gap, failure_probability, reversibility, importance, human_approval).
3. Check the 5 delegation triggers and 5 veto conditions.
4. Return both the human-readable summary AND the machine-readable Delegation Contract.

### 1. Human-Readable Output Format

```
RECOMMENDATION: DELEGATE | INLINE | HYBRID
CONFIDENCE: HIGH | MEDIUM | LOW
REASONING: <1-3 sentences>
SUB-AGENT TYPE: <parallel | context-branch | reviewer | verifier | sandbox>

GOAL:
<Precise, scoped objective for the sub-agent>

CONTEXT:
INCLUDE: <file globs>
EXCLUDE: <file globs, e.g. .git/**, secrets/**>

AUTHORITY:
READ: <allowed globs>
WRITE: <strictly bounded write globs, or none>
EXECUTE: <allowed commands/tools, or none>

FORBIDDEN:
<explicitly denied patterns, e.g. .git/**, git reset --hard, delete, repository structure changes>

VERIFICATION:
<Verification steps before marking DONE: tests, diffs, lint, manual review>

RETURN:
<Structured findings, evidence, uncertainty, artifacts>

ROLLBACK:
<Rollback strategy if verification fails or boundary breached>

BUDGET:
MAX_TOKENS: <e.g. 20000>
MAX_DURATION_SECONDS: <e.g. 300>

RISK:
LOW | MEDIUM | HIGH
```

### 2. Machine-Readable Delegation Contract

```yaml
delegation:
  id: "delegate-<task-id>"
  goal: "<scoped goal>"
  context:
    include:
      - "<path-glob>"
    exclude:
      - ".git/**"
      - "secrets/**"
  authority:
    read:
      - "<path-glob>"
    write:
      - "<path-glob>"
    execute:
      - "<cmd>"
    deny:
      - "git push*"
      - "git reset --hard*"
      - "git clean*"
      - "rm -rf*"
      - "delete"
      - ".git/**"
      - "repository structure changes"
  return:
    format: "structured"
    required:
      - "status"
      - "findings"
      - "evidence"
      - "uncertainty"
  verification:
    required: true
    commands:
      - "<verification command>"
  budget:
    max_tokens: 20000
    max_duration_seconds: 300
```

> **Enforcement Note:** The delegation contract is an enforceable authority boundary enforced by the `subagent-guard` runtime tool, not merely prompt guidance.

If the user provided no specific task, ask what they want to evaluate.

---

Usage: `/delegate [task or plan description]`
Example: `/delegate explore all API endpoints in this codebase and map dependencies`
