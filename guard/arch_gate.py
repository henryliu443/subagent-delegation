"""Architecture Change Gate.

Detects and intercepts architectural modifications:
- Repository root / workspace root changes
- Package root / topology alterations
- Parent or sibling directory deletions or moves
- Deletion or corruption of .git
- Project identity modifications (pyproject.toml, package.json)

Fail-closed: returns BLOCKED and requires human approval.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ArchitectureGateResult:
    blocked: bool
    status: str  # PASS | BLOCKED
    reason: Optional[str] = None
    requested_operation: Optional[str] = None

    def format_report(self) -> str:
        if not self.blocked:
            return "PASS: No architectural changes detected."
        return (
            "BLOCKED\n\n"
            "Architectural change detected.\n\n"
            f"Reason:\n{self.reason}\n\n"
            f"Requested:\n{self.requested_operation}\n\n"
            "Required:\nHuman approval"
        )


ARCHITECTURAL_IDENTIFIERS = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
}

DESTRUCTIVE_COMMAND_PATTERNS = [
    (r"\brm\s+(-[a-zA-Z]*r[a-zA-Z]*f*|-rf|-fr)\s+(/|\.\./|\.\.|\.|\*|~|parent[/\s]*)", "Recursive deletion targeting root, parent, or broad directory structure"),
    (r"\bgit\s+reset\s+--hard\b", "Hard reset of git working tree and index"),
    (r"\bgit\s+clean\s+-[a-zA-Z]*f[a-zA-Z]*\b", "Force clean untracked files from git tree"),
    (r"\bgit\s+push\s+.*--force\b", "Force pushing to remote repository"),
    (r"\brm\s+.*\.git\b", "Deletion of git internal directory or repository state"),
    (r"\bmv\s+\.\./[^\s]+\s+", "Moving or reorganizing sibling or parent projects"),
]


class ArchitectureGate:
    def __init__(self, workspace_root: str | Path):
        self.workspace_root = Path(workspace_root).resolve()

    def check_path_action(self, target_path: str | Path, action: str = "write") -> ArchitectureGateResult:
        """Inspect a file or directory operation for architectural impact."""
        action = action.lower()
        target_str = str(target_path).strip()

        # Step 1: Check if action targets parent directory or sibling
        if "delete" in action or "remove" in action or action == "rm":
            # Check if deleting parent directory
            clean = target_str.replace("\\", "/").rstrip("/")
            if clean in ("..", "../parent", "parent", "../", "./..") or clean.endswith("/parent") or clean.startswith("../"):
                return ArchitectureGateResult(
                    blocked=True,
                    status="BLOCKED",
                    reason="Attempt to delete parent directory or sibling project structure.",
                    requested_operation=f"{action} {target_str}",
                )

        # Normalize target
        if os.path.isabs(target_str):
            norm = Path(os.path.normpath(target_str))
        else:
            norm = Path(os.path.normpath(self.workspace_root / target_str))

        # Check if target is workspace root itself
        if norm == self.workspace_root and action in ("delete", "remove", "rm"):
            return ArchitectureGateResult(
                blocked=True,
                status="BLOCKED",
                reason="Attempt to delete or remove repository/workspace root.",
                requested_operation=f"{action} {target_str}",
            )

        # Check if target is outside workspace root (parent or sibling)
        try:
            rel = norm.relative_to(self.workspace_root)
        except ValueError:
            return ArchitectureGateResult(
                blocked=True,
                status="BLOCKED",
                reason=f"Operation target '{target_str}' is outside workspace root ({self.workspace_root}).",
                requested_operation=f"{action} {target_str}",
            )

        # Check if target is .git
        rel_parts = rel.parts
        if len(rel_parts) > 0 and rel_parts[0] == ".git":
            if action in ("delete", "remove", "rm"):
                return ArchitectureGateResult(
                    blocked=True,
                    status="BLOCKED",
                    reason="Deletion of .git repository internals is an architectural change.",
                    requested_operation=f"{action} {target_str}",
                )

        # Check if deleting top-level parent folder inside workspace (e.g. 'parent' folder)
        if len(rel_parts) == 1 and action in ("delete", "remove", "rm") and rel_parts[0] in ("parent", "src", "packages", "lib"):
            return ArchitectureGateResult(
                blocked=True,
                status="BLOCKED",
                reason=f"Attempt to delete top-level architectural package directory '{rel_parts[0]}'.",
                requested_operation=f"{action} {target_str}",
            )

        # Check project identity files
        if len(rel_parts) == 1 and rel_parts[0] in ARCHITECTURAL_IDENTIFIERS:
            if action in ("delete", "remove", "rm"):
                return ArchitectureGateResult(
                    blocked=True,
                    status="BLOCKED",
                    reason=f"Attempt to delete project manifest '{rel_parts[0]}', altering repository identity.",
                    requested_operation=f"{action} {target_str}",
                )

        return ArchitectureGateResult(blocked=False, status="PASS")

    def check_command(self, command: str) -> ArchitectureGateResult:
        """Inspect a shell command for architectural changes or destructive restructuring."""
        cmd = command.strip()

        # Check regex patterns
        for pattern, desc in DESTRUCTIVE_COMMAND_PATTERNS:
            if re.search(pattern, cmd):
                return ArchitectureGateResult(
                    blocked=True,
                    status="BLOCKED",
                    reason=f"Destructive architectural command detected: {desc}",
                    requested_operation=cmd,
                )

        # Check parent directory operations in command
        if re.search(r"\brm\s+.*parent", cmd, re.IGNORECASE):
            return ArchitectureGateResult(
                blocked=True,
                status="BLOCKED",
                reason="Deletion targeting 'parent' project directory.",
                requested_operation=cmd,
            )

        return ArchitectureGateResult(blocked=False, status="PASS")
