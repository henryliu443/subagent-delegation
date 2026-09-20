Run the Sub-Agent Delegation decision model on the following task or plan.

Read `SKILL.md` in the project root first. Then:

1. Identify the task or plan provided by the user
2. Evaluate it against the 13 input factors (complexity, context_size, context_contamination, parallelism, independence, verification_value, latency, token_cost, model_capability_gap, failure_probability, reversibility, importance, human_approval)
3. Check the 5 delegation triggers and 5 veto conditions
4. Return a structured recommendation:

```
RECOMMENDATION: DELEGATE | INLINE | HYBRID
Confidence: high | medium | low
Reasoning: <1-3 sentences>
Sub-agent type (if delegate): <parallel | context-branch | reviewer | verifier | sandbox>
Return contract: <what flows back>
Risk: <what could go wrong>
```

If the user provided no specific task, ask what they want to evaluate.

---

Usage: `/delegate [task or plan description]`
Example: `/delegate explore all API endpoints in this codebase and map dependencies`
