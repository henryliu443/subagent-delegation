#!/usr/bin/env python3
"""Executable verification demo for Subagent Delegation Runtime Guard.

Runs the 6 mandatory boundary and gate test cases:
1. child-a/test.txt (write) -> Should SUCCEED (ALLOW)
2. child-b/test.txt (write) -> Should FAIL (DENY)
3. ../parent (write) -> Should FAIL (DENY)
4. .git/config (access) -> Should FAIL (DENY)
5. delete parent/ -> Should trigger ARCHITECTURE GATE (BLOCKED)
6. read child-a/** -> Should PASS (ALLOW)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add project root to sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from guard.arch_gate import ArchitectureGate
from guard.contract import load_contract
from guard.path_guard import PathGuard


def run_demo() -> bool:
    contract_path = SCRIPT_DIR / "contract.json"
    contract = load_contract(contract_path)
    workspace_root = SCRIPT_DIR / "parent"

    arch_gate = ArchitectureGate(workspace_root=workspace_root)
    path_guard = PathGuard(workspace_root=workspace_root, contract=contract)

    print("================================================================================")
    print("SUBAGENT DELEGATION RUNTIME GUARD DEMO")
    print("================================================================================")
    print(f"Contract ID:     {contract.id}")
    print(f"Workspace Root:  {workspace_root}")
    print(f"Write Authority: {contract.authority.write}")
    print(f"Read Authority:  {contract.authority.read}")
    print(f"Deny Authority:  {contract.authority.deny}")
    print("--------------------------------------------------------------------------------\n")

    test_cases = [
        {
            "id": 1,
            "name": "Write inside authorized scope",
            "target": "child-a/test.txt",
            "action": "write",
            "expected_verdict": "ALLOW",
            "expect_arch_gate": False,
        },
        {
            "id": 2,
            "name": "Write to unauthorized sibling directory",
            "target": "child-b/test.txt",
            "action": "write",
            "expected_verdict": "DENY",
            "expect_arch_gate": False,
        },
        {
            "id": 3,
            "name": "Directory traversal outside workspace root",
            "target": "../parent",
            "action": "write",
            "expected_verdict": "DENY",
            "expect_arch_gate": False,
        },
        {
            "id": 4,
            "name": "Access protected .git internal directory",
            "target": ".git/config",
            "action": "read",
            "expected_verdict": "DENY",
            "expect_arch_gate": False,
        },
        {
            "id": 5,
            "name": "Attempt to delete parent directory",
            "target": "parent/",
            "action": "delete",
            "expected_verdict": "BLOCKED",
            "expect_arch_gate": True,
        },
        {
            "id": 6,
            "name": "Read inside authorized scope",
            "target": "child-a/test.txt",
            "action": "read",
            "expected_verdict": "ALLOW",
            "expect_arch_gate": False,
        },
    ]

    all_passed = True
    results_table = []

    for tc in test_cases:
        target = tc["target"]
        action = tc["action"]

        # Step 1: Architecture gate
        arch_res = arch_gate.check_path_action(target, action=action)
        if tc["expect_arch_gate"]:
            if arch_res.blocked:
                status = "BLOCKED"
                reason = arch_res.reason
                passed = True
            else:
                status = "PASS"
                reason = "Architecture gate failed to intercept"
                passed = False
        else:
            if arch_res.blocked:
                status = "BLOCKED"
                reason = arch_res.reason
                passed = False
            else:
                # Step 2: Path boundary check
                path_res = path_guard.check(target, action=action)
                status = path_res.status
                reason = path_res.reason
                passed = (status == tc["expected_verdict"])

        if not passed:
            all_passed = False

        verdict_str = "PASS" if passed else "FAIL"
        results_table.append({
            "id": tc["id"],
            "name": tc["name"],
            "action": action,
            "target": target,
            "expected": tc["expected_verdict"],
            "actual": status,
            "reason": reason,
            "verdict": verdict_str,
        })

    # Print Detailed Outputs
    for row in results_table:
        print(f"Test #{row['id']}: {row['name']}")
        print(f"  Action:   {row['action'].upper()} -> {row['target']}")
        print(f"  Expected: {row['expected']}")
        print(f"  Actual:   {row['actual']}")
        print(f"  Reason:   {row['reason']}")
        print(f"  Result:   [{row['verdict']}]\n")

    # Print Summary Table
    print("================================================================================")
    print("DEMO VERIFICATION SUMMARY TABLE")
    print("================================================================================")
    print(f"{'#':<3} | {'Target':<22} | {'Action':<6} | {'Expected':<8} | {'Actual':<8} | {'Verdict'}")
    print("-" * 65)
    for row in results_table:
        print(f"{row['id']:<3} | {row['target']:<22} | {row['action']:<6} | {row['expected']:<8} | {row['actual']:<8} | {row['verdict']}")
    print("-" * 65)
    print(f"OVERALL STATUS: {'PASS' if all_passed else 'FAIL'}")
    print("================================================================================\n")

    return all_passed


if __name__ == "__main__":
    success = run_demo()
    sys.exit(0 if success else 1)
