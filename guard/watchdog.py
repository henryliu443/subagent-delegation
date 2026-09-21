"""Lightweight Watchdog for runaway, stalled, and unexpected state changes.

Monitors execution state:
- Current working directory vs workspace boundaries
- Working tree modifications vs contract write boundaries
- Stalled progress / inactivity duration
- Repeated execution failures

Fail-closed: triggers PAUSE / BLOCK and returns control to human/main agent.
No auto-restart. No auto-recovery. No unauthorized self-repair.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from guard.contract import DelegationContract
from guard.path_guard import PathGuard


@dataclass
class WatchdogViolation:
    violation_type: str  # BOUNDARY_VIOLATION | UNEXPECTED_MODIFICATION | PROTECTED_PATH | INACTIVITY_TIMEOUT | REPEATED_FAILURE
    details: str
    diagnostics: dict


@dataclass
class WatchdogResult:
    ok: bool
    status: str  # OK | PAUSE_BLOCK
    violation: Optional[WatchdogViolation] = None

    def format_report(self) -> str:
        if self.ok:
            return "WATCHDOG OK: No anomalies or contract boundary violations detected."
        v = self.violation
        diagnostics = v.diagnostics if (v and v.diagnostics) else {}
        diag_lines = [f"- {k}: {val}" for k, val in diagnostics.items()]
        return (
            "PAUSE / BLOCK\n\n"
            "Watchdog violation detected:\n"
            f"Type: {v.violation_type if v else 'UNKNOWN'}\n"
            f"Details: {v.details if v else 'Unknown anomaly'}\n\n"
            "Diagnostics:\n"
            + ("\n".join(diag_lines) if diag_lines else "- none")
            + "\n\n"
            "Action:\n"
            "Halt execution immediately. Control returned to main agent / human.\n"
            "Automatic recovery disabled."
        )


class Watchdog:
    def __init__(
        self,
        workspace_root: str | Path,
        contract: DelegationContract,
        state_file: Optional[str | Path] = None,
        max_inactivity_seconds: int = 120,
        max_failures: int = 3,
    ):
        self.workspace_root = Path(workspace_root).resolve()
        self.contract = contract
        self.path_guard = PathGuard(self.workspace_root, self.contract)
        self.state_file = Path(state_file).resolve() if state_file else self.workspace_root / ".guard" / "watchdog_state.json"
        self.max_inactivity_seconds = max_inactivity_seconds
        self.max_failures = max_failures

    def _init_state(self) -> dict:
        now = time.time()
        return {
            "task_id": self.contract.id,
            "start_time": now,
            "last_action_time": now,
            "failure_count": 0,
            "status": "RUNNING",
        }

    def load_state(self) -> dict:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        st = self._init_state()
        self.save_state(st)
        return st

    def save_state(self, state: dict) -> None:
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception:
            pass

    def record_heartbeat(self, failure: bool = False) -> None:
        st = self.load_state()
        st["last_action_time"] = time.time()
        if failure:
            st["failure_count"] = st.get("failure_count", 0) + 1
        else:
            st["failure_count"] = 0
        self.save_state(st)

    def inspect(self, current_cwd: Optional[str | Path] = None) -> WatchdogResult:
        """Run a single audit check against the current environment and task state."""
        cwd_to_check = Path(current_cwd or os.getcwd()).resolve()
        state = self.load_state()
        now = time.time()

        # 1. CWD boundary check
        try:
            cwd_to_check.relative_to(self.workspace_root)
        except ValueError:
            return WatchdogResult(
                ok=False,
                status="PAUSE_BLOCK",
                violation=WatchdogViolation(
                    violation_type="BOUNDARY_VIOLATION",
                    details=f"Current working directory '{cwd_to_check}' escaped workspace root '{self.workspace_root}'",
                    diagnostics={"cwd": str(cwd_to_check), "workspace_root": str(self.workspace_root)},
                ),
            )

        # 2. Git status / modified files check
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
                    lines = [l.strip() for l in proc.stdout.splitlines() if l.strip()]
                    for l in lines:
                        file_path = l[3:].strip()
                        if " -> " in file_path:
                            file_path = file_path.split(" -> ")[1].strip()
                        if prefix and file_path.startswith(prefix):
                            file_path = file_path[len(prefix):]
                        if not file_path:
                            continue

                        # Check .git internal
                        if file_path == ".git" or file_path.startswith(".git/"):
                            return WatchdogResult(
                                ok=False,
                                status="PAUSE_BLOCK",
                                violation=WatchdogViolation(
                                    violation_type="PROTECTED_PATH",
                                    details=f"Modification detected inside protected directory: {file_path}",
                                    diagnostics={"file": file_path},
                                ),
                            )

                        check = self.path_guard.check(file_path, action="write")
                        if not check.allowed:
                            return WatchdogResult(
                                ok=False,
                                status="PAUSE_BLOCK",
                                violation=WatchdogViolation(
                                    violation_type="UNEXPECTED_MODIFICATION",
                                    details=f"File changed outside write boundary: '{file_path}' ({check.reason})",
                                    diagnostics={"file": file_path, "rule": check.matched_rule},
                                ),
                            )
        except Exception:
            pass

        # 3. Inactivity / stall check
        last_action = state.get("last_action_time", now)
        elapsed = now - last_action
        if elapsed > self.max_inactivity_seconds:
            return WatchdogResult(
                ok=False,
                status="PAUSE_BLOCK",
                violation=WatchdogViolation(
                    violation_type="INACTIVITY_TIMEOUT",
                    details=f"Task stalled: no activity detected for {int(elapsed)}s (threshold: {self.max_inactivity_seconds}s)",
                    diagnostics={"elapsed_seconds": int(elapsed), "threshold_seconds": self.max_inactivity_seconds},
                ),
            )

        # 4. Repeated failure check
        fail_count = state.get("failure_count", 0)
        if fail_count >= self.max_failures:
            return WatchdogResult(
                ok=False,
                status="PAUSE_BLOCK",
                violation=WatchdogViolation(
                    violation_type="REPEATED_FAILURE",
                    details=f"Repeated execution failures reached limit: {fail_count} >= {self.max_failures}",
                    diagnostics={"failure_count": fail_count, "max_failures": self.max_failures},
                ),
            )

        return WatchdogResult(ok=True, status="OK")

    def run_loop(self, interval_seconds: int = 20, max_iterations: Optional[int] = None) -> int:
        """Periodic background poll loop (~20s interval)."""
        iterations = 0
        while True:
            res = self.inspect()
            if not res.ok:
                print(res.format_report())
                return 1
            iterations += 1
            if max_iterations and iterations >= max_iterations:
                return 0
            time.sleep(interval_seconds)
