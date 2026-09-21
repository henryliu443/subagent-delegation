"""CLI Entrypoint for Delegation Runtime Guard.

Provides machine-enforced boundary checks, architecture gates, verification gates, and watchdog.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from guard.arch_gate import ArchitectureGate
from guard.contract import DelegationContract, load_contract
from guard.path_guard import PathGuard
from guard.verify_gate import VerificationGate
from guard.watchdog import Watchdog


def cmd_check_path(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    workspace_root = Path(args.root or os.getcwd()).resolve()

    # Step 1: Architecture gate check
    arch_gate = ArchitectureGate(workspace_root)
    arch_res = arch_gate.check_path_action(args.path, action=args.action)
    if arch_res.blocked:
        print(arch_res.format_report())
        return 1

    # Step 2: Path boundary check
    path_guard = PathGuard(workspace_root, contract)
    res = path_guard.check(args.path, action=args.action)

    if res.status == "ALLOW":
        print(f"ALLOW: {res.reason} [{res.target_path}]")
        return 0
    elif res.status == "ASK":
        print(f"ASK: Human approval required. Reason: {res.reason} [{res.target_path}]")
        return 2
    else:
        print(f"DENY: {res.reason} [{res.target_path}]")
        return 1


def cmd_check_cmd(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    workspace_root = Path(args.root or os.getcwd()).resolve()

    # Step 1: Architecture gate check
    arch_gate = ArchitectureGate(workspace_root)
    arch_res = arch_gate.check_command(args.cmd)
    if arch_res.blocked:
        print(arch_res.format_report())
        return 1

    cmd_str = args.cmd.strip()

    # Step 2: Deny list check
    for deny_pat in contract.authority.deny:
        pat = deny_pat.rstrip("*").strip()
        if pat and (cmd_str == pat or cmd_str.startswith(pat)):
            print(f"DENY: Command '{cmd_str}' explicitly forbidden by contract authority ('{deny_pat}')")
            return 1

    # Step 3: Execute allow list check
    if contract.authority.execute:
        matched = False
        for exe in contract.authority.execute:
            exe_clean = exe.rstrip("*").strip()
            if cmd_str == exe_clean or cmd_str.startswith(exe_clean):
                matched = True
                break
        if matched:
            print(f"ALLOW: Command '{cmd_str}' permitted by contract execute authority.")
            return 0
        else:
            print(f"ASK: Command '{cmd_str}' not in contract execute list {contract.authority.execute}. Human approval required.")
            return 2

    print(f"ALLOW: Command '{cmd_str}' permitted.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    workspace_root = Path(args.root or os.getcwd()).resolve()
    gate = VerificationGate(workspace_root, contract)
    res = gate.run_verification()
    print(res.format_report())
    return 0 if res.passed else 1


def cmd_watchdog(args: argparse.Namespace) -> int:
    contract = load_contract(args.contract)
    workspace_root = Path(args.root or os.getcwd()).resolve()
    wd = Watchdog(
        workspace_root=workspace_root,
        contract=contract,
        max_inactivity_seconds=args.max_inactivity,
    )
    if args.once:
        res = wd.inspect()
        print(res.format_report())
        return 0 if res.ok else 1
    else:
        return wd.run_loop(interval_seconds=args.interval)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="subagent-guard",
        description="Runtime Guard for Coding Agent Delegation Contracts",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check-path
    p_path = subparsers.add_parser("check-path", help="Check if a file/dir path operation is permitted")
    p_path.add_argument("--contract", required=True, help="Path to delegation contract YAML/JSON")
    p_path.add_argument("--path", required=True, help="Target file or directory path")
    p_path.add_argument("--action", default="write", choices=["read", "write", "delete"], help="Operation type")
    p_path.add_argument("--root", default=None, help="Workspace root directory (defaults to cwd)")

    # check-cmd
    p_cmd = subparsers.add_parser("check-cmd", help="Check if a shell command is permitted")
    p_cmd.add_argument("--contract", required=True, help="Path to delegation contract YAML/JSON")
    p_cmd.add_argument("--cmd", required=True, help="Shell command to inspect")
    p_cmd.add_argument("--root", default=None, help="Workspace root directory (defaults to cwd)")

    # verify
    p_ver = subparsers.add_parser("verify", help="Run verification gate before marking task DONE")
    p_ver.add_argument("--contract", required=True, help="Path to delegation contract YAML/JSON")
    p_ver.add_argument("--root", default=None, help="Workspace root directory (defaults to cwd)")

    # watchdog
    p_wd = subparsers.add_parser("watchdog", help="Audit or continuously monitor agent execution state")
    p_wd.add_argument("--contract", required=True, help="Path to delegation contract YAML/JSON")
    p_wd.add_argument("--root", default=None, help="Workspace root directory (defaults to cwd)")
    p_wd.add_argument("--once", action="store_true", help="Run a single audit check and exit")
    p_wd.add_argument("--interval", type=int, default=20, help="Poll interval in seconds (default: 20)")
    p_wd.add_argument("--max-inactivity", type=int, default=120, help="Max inactivity threshold in seconds")

    args = parser.parse_args()

    if args.command == "check-path":
        sys.exit(cmd_check_path(args))
    elif args.command == "check-cmd":
        sys.exit(cmd_check_cmd(args))
    elif args.command == "verify":
        sys.exit(cmd_verify(args))
    elif args.command == "watchdog":
        sys.exit(cmd_watchdog(args))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
