"""Delegation Contract model and JSON loader.

JSON is the ONLY runtime contract format. No custom YAML parser.
YAML may appear in documentation as an illustration, but it is never parsed at runtime.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class ContextConfig:
    include: List[str] = field(default_factory=lambda: ["**"])
    exclude: List[str] = field(default_factory=lambda: [".git/**", "**/.env*", "**/secrets/**"])


@dataclass
class AuthorityConfig:
    read: List[str] = field(default_factory=lambda: ["**"])
    write: List[str] = field(default_factory=list)
    execute: List[str] = field(default_factory=list)
    deny: List[str] = field(default_factory=lambda: [
        "git push*",
        "git reset --hard*",
        "git clean*",
        "rm -rf*",
        "delete",
        ".git/**",
        "repository structure changes",
    ])


@dataclass
class ReturnConfig:
    format: str = "structured"
    required: List[str] = field(default_factory=lambda: ["status", "findings", "evidence", "uncertainty"])


@dataclass
class VerificationConfig:
    required: bool = True
    commands: List[str] = field(default_factory=list)


@dataclass
class BudgetConfig:
    max_tokens: int = 20000
    max_duration_seconds: int = 300


@dataclass
class DelegationContract:
    id: str
    goal: str
    context: ContextConfig = field(default_factory=ContextConfig)
    authority: AuthorityConfig = field(default_factory=AuthorityConfig)
    return_config: ReturnConfig = field(default_factory=ReturnConfig)
    verification: VerificationConfig = field(default_factory=VerificationConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DelegationContract":
        d = data.get("delegation", data)
        contract_id = str(d.get("id", "contract-unspecified"))
        goal = str(d.get("goal", ""))

        ctx_raw = d.get("context", {}) or {}
        context = ContextConfig(
            include=list(ctx_raw.get("include", ["**"])),
            exclude=list(ctx_raw.get("exclude", [".git/**", "**/.env*", "**/secrets/**"])),
        )

        auth_raw = d.get("authority", {}) or {}
        authority = AuthorityConfig(
            read=list(auth_raw.get("read", ["**"])),
            write=list(auth_raw.get("write", [])),
            execute=list(auth_raw.get("execute", [])),
            deny=list(auth_raw.get("deny", [
                "git push*",
                "git reset --hard*",
                "git clean*",
                "rm -rf*",
                "delete",
                ".git/**",
                "repository structure changes",
            ])),
        )

        ret_raw = d.get("return", {}) or {}
        return_config = ReturnConfig(
            format=str(ret_raw.get("format", "structured")),
            required=list(ret_raw.get("required", ["status", "findings", "evidence", "uncertainty"])),
        )

        ver_raw = d.get("verification", {})
        if isinstance(ver_raw, bool):
            verification = VerificationConfig(required=ver_raw)
        else:
            ver_raw = ver_raw or {}
            verification = VerificationConfig(
                required=bool(ver_raw.get("required", True)),
                commands=list(ver_raw.get("commands", [])),
            )

        bud_raw = d.get("budget", {}) or {}
        budget = BudgetConfig(
            max_tokens=int(bud_raw.get("max_tokens", 20000)),
            max_duration_seconds=int(bud_raw.get("max_duration_seconds", 300)),
        )

        return cls(
            id=contract_id,
            goal=goal,
            context=context,
            authority=authority,
            return_config=return_config,
            verification=verification,
            budget=budget,
            raw_data=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delegation": {
                "id": self.id,
                "goal": self.goal,
                "context": {"include": self.context.include, "exclude": self.context.exclude},
                "authority": {
                    "read": self.authority.read,
                    "write": self.authority.write,
                    "execute": self.authority.execute,
                    "deny": self.authority.deny,
                },
                "return": {"format": self.return_config.format, "required": self.return_config.required},
                "verification": {
                    "required": self.verification.required,
                    "commands": self.verification.commands,
                },
                "budget": {
                    "max_tokens": self.budget.max_tokens,
                    "max_duration_seconds": self.budget.max_duration_seconds,
                },
            }
        }


def load_contract(path_or_content: str | Path) -> DelegationContract:
    """Load and validate a DelegationContract from a JSON file path or raw JSON string."""
    content: str
    if isinstance(path_or_content, Path) or (
        isinstance(path_or_content, str) and os.path.exists(path_or_content)
    ):
        content = Path(path_or_content).read_text(encoding="utf-8")
    else:
        content = str(path_or_content)

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Delegation Contract must be valid JSON (runtime format is JSON only): {e}"
        ) from e

    if not isinstance(data, dict):
        raise ValueError("Delegation Contract must be a JSON object")

    return DelegationContract.from_dict(data)
