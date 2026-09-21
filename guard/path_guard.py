"""Path boundary enforcer.

Validates requested path operations against workspace boundaries and delegation contracts.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from guard.contract import DelegationContract


@dataclass
class PathCheckResult:
    allowed: bool
    status: str  # ALLOW | DENY | ASK
    reason: str
    target_path: str
    normalized_path: str
    matched_rule: Optional[str] = None


def glob_to_regex(pattern: str) -> re.Pattern:
    """Compile glob pattern supporting **, *, and standard wildcards."""
    pattern = pattern.replace("\\", "/").strip()
    res = "^"
    i = 0
    n = len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                i += 2
                if i < n and pattern[i] == "/":
                    res += "(?:.*/)?"
                    i += 1
                else:
                    res += ".*"
            else:
                res += "[^/]*"
                i += 1
        elif c == "?":
            res += "[^/]"
            i += 1
        elif c in ".^$+-=!:|()[]{}":
            res += re.escape(c)
            i += 1
        else:
            res += re.escape(c)
            i += 1
    res += "$"
    return re.compile(res)


def match_glob_list(path_str: str, patterns: List[str]) -> tuple[bool, Optional[str]]:
    """Match a normalized relative path against a list of glob patterns."""
    clean_path = path_str.replace("\\", "/").strip("/")
    for pat in patterns:
        clean_pat = pat.replace("\\", "/").strip()
        # Direct folder prefix check if pattern ends with /**
        if clean_pat.endswith("/**"):
            prefix = clean_pat[:-3].strip("/")
            if clean_path == prefix or clean_path.startswith(prefix + "/"):
                return True, pat
        # Regex check
        try:
            rx = glob_to_regex(clean_pat)
            if rx.match(clean_path):
                return True, pat
        except Exception:
            pass
    return False, None


class PathGuard:
    def __init__(self, workspace_root: str | Path, contract: DelegationContract):
        self.workspace_root = Path(workspace_root).resolve()
        self.contract = contract

    def check(self, target_path: str | Path, action: str = "write") -> PathCheckResult:
        """Check if action ('read' | 'write' | 'delete') on target_path is permitted."""
        action = action.lower()
        target_str = str(target_path).strip()

        # Step 1: Detect explicit path traversal attempts in raw input
        raw_parts = Path(target_str).parts
        if ".." in raw_parts:
            return PathCheckResult(
                allowed=False,
                status="DENY",
                reason=f"Path traversal violation: '{target_str}' contains forbidden '..' traversal sequence",
                target_path=target_str,
                normalized_path=str(norm_path if 'norm_path' in locals() else target_str),
            )

        # Step 2: Canonicalize path
        if os.path.isabs(target_str):
            norm_path = Path(os.path.normpath(target_str))
        else:
            norm_path = Path(os.path.normpath(self.workspace_root / target_str))

        # Check if path escapes workspace root
        try:
            rel_to_root = norm_path.relative_to(self.workspace_root)
            rel_str = str(rel_to_root).replace("\\", "/")
        except ValueError:
            # Traversed outside workspace root
            return PathCheckResult(
                allowed=False,
                status="DENY",
                reason=f"Path boundary violation: '{target_str}' escapes workspace root '{self.workspace_root}'",
                target_path=target_str,
                normalized_path=str(norm_path),
            )

        # Step 3: Check protected system paths (.git, .env, secrets)
        rel_parts = rel_to_root.parts
        if ".git" in rel_parts:
            return PathCheckResult(
                allowed=False,
                status="DENY",
                reason=f"Access denied: '.git' internal directory is strictly protected",
                target_path=target_str,
                normalized_path=str(norm_path),
                matched_rule=".git/**",
            )

        # Step 4: Check contract context exclusions
        excluded, rule = match_glob_list(rel_str, self.contract.context.exclude)
        if excluded:
            return PathCheckResult(
                allowed=False,
                status="DENY",
                reason=f"Excluded path: matches context exclusion '{rule}'",
                target_path=target_str,
                normalized_path=str(norm_path),
                matched_rule=rule,
            )

        # Step 5: Check contract deny patterns
        denied, rule = match_glob_list(rel_str, self.contract.authority.deny)
        if denied:
            return PathCheckResult(
                allowed=False,
                status="DENY",
                reason=f"Forbidden path: explicitly denied by contract authority ('{rule}')",
                target_path=target_str,
                normalized_path=str(norm_path),
                matched_rule=rule,
            )

        # Step 6: Check action-specific authority
        if action == "read":
            matched, rule = match_glob_list(rel_str, self.contract.authority.read)
            if matched or "*" in self.contract.authority.read or "**" in self.contract.authority.read:
                return PathCheckResult(
                    allowed=True,
                    status="ALLOW",
                    reason="Path allowed for read",
                    target_path=target_str,
                    normalized_path=str(norm_path),
                    matched_rule=rule or "**",
                )
            return PathCheckResult(
                allowed=False,
                status="DENY",
                reason=f"Read permission denied: '{rel_str}' not covered by read authority {self.contract.authority.read}",
                target_path=target_str,
                normalized_path=str(norm_path),
            )

        elif action == "write":
            matched, rule = match_glob_list(rel_str, self.contract.authority.write)
            if matched:
                return PathCheckResult(
                    allowed=True,
                    status="ALLOW",
                    reason="Path allowed for write",
                    target_path=target_str,
                    normalized_path=str(norm_path),
                    matched_rule=rule,
                )
            return PathCheckResult(
                allowed=False,
                status="DENY",
                reason=f"Write boundary violation: '{rel_str}' is outside authorized write patterns {self.contract.authority.write}",
                target_path=target_str,
                normalized_path=str(norm_path),
            )

        elif action == "delete":
            # Deletions are destructive by default
            if "delete" in [d.lower() for d in self.contract.authority.deny]:
                return PathCheckResult(
                    allowed=False,
                    status="DENY",
                    reason="Delete operations are explicitly forbidden by contract deny list",
                    target_path=target_str,
                    normalized_path=str(norm_path),
                    matched_rule="delete",
                )
            matched, rule = match_glob_list(rel_str, self.contract.authority.write)
            if not matched:
                return PathCheckResult(
                    allowed=False,
                    status="DENY",
                    reason=f"Delete violation: path '{rel_str}' is outside write authority",
                    target_path=target_str,
                    normalized_path=str(norm_path),
                )
            # Within write authority, but still destructive
            return PathCheckResult(
                allowed=False,
                status="ASK",
                reason=f"Destructive deletion within authorized directory requires explicit confirmation",
                target_path=target_str,
                normalized_path=str(norm_path),
            )

        return PathCheckResult(
            allowed=False,
            status="DENY",
            reason=f"Unknown action: '{action}'",
            target_path=target_str,
            normalized_path=str(norm_path),
        )
