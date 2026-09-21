"""Verification Gate.

Enforces that an agent cannot mark a task as DONE without passing verification:
EXECUTE -> VERIFY -> PASS -> DONE

Validates:
1. File modification boundaries (git status against authority.write)
2. Contract verification commands (tests, lint, build, diff checks)
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from guard.contract import DelegationContract
from guard.path_guard import PathGuard


@dataclass
class VerificationResult:
    passed: bool
    status: str  # PASS | REJECTED
    reason: Optional[str] = None
    command_outputs: Optional[List[dict]] = None

    def format_report(self) -> str:
        if self.passed:
            return (
                "VERIFICATION PASSED\n\n"
                "All contract verification checks and boundary invariants passed.\n"
                "State transition: DONE"
            )
        return (
            "COMPLETION REJECTED\n\n"
            f"Reason:\n{self.reason}\n\n"
            "Action:\nHand control back to agent with failure diagnostics."
        )


class VerificationGate:
    def __init__(self, workspace_root: str | Path, contract: DelegationContract):
        self.workspace_root = Path(workspace_root).resolve()
        self.contract = contract
        self.path_guard = PathGuard(self.workspace_root, self.contract)

    def run_verification(self) -> VerificationResult:
        # Step 1: Invariant check on git modified files
        try:
            prefix_proc = subprocess.run(
                ["git", "rev-parse", "--show-prefix"],
                cwd=str(self.workspace_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if prefix_proc.returncode == 0:
                prefix = prefix_proc.stdout.strip()
                proc = subprocess.run(
                    ["git", "status", "--porcelain", "-uall", "--", "."],
                    cwd=str(self.workspace_root),
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if proc.returncode == 0:
                    changed_lines = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
                    unauthorized_files = []
                    for line in changed_lines:
                        file_path = line[3:].strip()
                        if " -> " in file_path:
                            file_path = file_path.split(" -> ")[1].strip()
                        if prefix and file_path.startswith(prefix):
                            file_path = file_path[len(prefix):]
                        if not file_path:
                            continue
                        check = self.path_guard.check(file_path, action="write")
                        if not check.allowed:
                            unauthorized_files.append(f"{file_path} ({check.reason})")

                    if unauthorized_files:
                        return VerificationResult(
                            passed=False,
                            status="REJECTED",
                            reason="Unauthorized files were modified outside write boundary:\n"
                            + "\n".join(f"- {f}" for f in unauthorized_files),
                        )
        except Exception as e:
            return VerificationResult(
                passed=False,
                status="REJECTED",
                reason=f"Failed to inspect git working tree status: {e}",
            )

        # Step 2: Run configured verification commands
        commands = self.contract.verification.commands
        cmd_results = []
        for cmd in commands:
            cmd_clean = cmd.strip()
            if not cmd_clean:
                continue
            try:
                proc = subprocess.run(
                    cmd_clean,
                    shell=True,
                    cwd=str(self.workspace_root),
                    capture_output=True,
                    text=True,
                    timeout=self.contract.budget.max_duration_seconds,
                )
                cmd_results.append({
                    "command": cmd_clean,
                    "exit_code": proc.returncode,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip(),
                })
                if proc.returncode != 0:
                    err_msg = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
                    return VerificationResult(
                        passed=False,
                        status="REJECTED",
                        reason=f"Verification command failed: '{cmd_clean}' (exit code {proc.returncode})\nOutput:\n{err_msg}",
                        command_outputs=cmd_results,
                    )
            except subprocess.TimeoutExpired:
                return VerificationResult(
                    passed=False,
                    status="REJECTED",
                    reason=f"Verification command timed out after {self.contract.budget.max_duration_seconds}s: '{cmd_clean}'",
                    command_outputs=cmd_results,
                )
            except Exception as ex:
                return VerificationResult(
                    passed=False,
                    status="REJECTED",
                    reason=f"Execution error running verification '{cmd_clean}': {ex}",
                    command_outputs=cmd_results,
                )

        return VerificationResult(passed=True, status="PASS", command_outputs=cmd_results)
