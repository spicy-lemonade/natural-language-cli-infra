"""
Claude pretooluse hook for blocking destructive bash commands.

Contract:
- exit 0  => allow
- exit !=0 => block (must emit JSON with reason)

Features:
- Splits multi-command input on ;, &&, ||, | while respecting quotes
- Blocks dangerous system-level commands
- Blocks destructive file operations outside project root
- Blocks network tools (curl, wget, etc.)
- Allows only read-only git commands
- Blocks dangerous shell expansions and redirects
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

EXIT_ALLOW = 0
EXIT_BLOCK = 1

# Git commands that are read-only and safe
GIT_READ_COMMANDS = frozenset({
    "status", "log", "diff", "show", "branch", "tag", "remote",
    "ls-files", "ls-tree", "rev-parse", "describe", "shortlog",
    "blame", "grep", "reflog", "config", "stash", "help", "version",
    "rev-list", "cat-file", "ls-remote", "for-each-ref", "name-rev",
    "symbolic-ref", "verify-commit", "verify-tag", "whatchanged",
})

# System commands that are always blocked
BLOCKED_SYSTEM_COMMANDS = frozenset({
    "dd", "wipefs", "mount", "umount", "fdisk", "parted", "mkswap",
    "swapon", "swapoff", "losetup", "cryptsetup", "lvm", "vgcreate",
    "vgremove", "lvcreate", "lvremove", "shutdown", "reboot", "halt",
    "poweroff", "init", "systemctl", "service",
})

# Network/download commands that are blocked
BLOCKED_NETWORK_COMMANDS = frozenset({
    "curl", "wget", "nc", "netcat", "ncat", "socat", "telnet",
    "ftp", "sftp", "scp", "rsync",
})

# Package manager destructive commands
BLOCKED_PACKAGE_PATTERNS = [
    (re.compile(r"^(pip3?|python3?\s+-m\s+pip)"), ["uninstall", "cache"]),
    (re.compile(r"^npm"), ["uninstall", "remove", "rm", "prune", "cache"]),
    (re.compile(r"^yarn"), ["remove", "cache"]),
    (re.compile(r"^brew"), ["uninstall", "remove", "cleanup", "autoremove"]),
]


def block(msg: str) -> None:
    """Emit JSON reason and exit with block code."""
    print(json.dumps({"action": "block", "reason": msg}))
    sys.exit(EXIT_BLOCK)


def split_commands(cmd: str) -> list[str]:
    """
    Split a bash command string into individual subcommands.

    Handles compound commands separated by ; && || |
    while respecting quoted strings.
    """
    # Regex to match quoted strings or shell operators
    # This preserves quotes and splits on operators
    token_pattern = re.compile(
        r"""
        (?P<dquote>"(?:[^"\\]|\\.)*") |  # double-quoted string
        (?P<squote>'[^']*') |             # single-quoted string
        (?P<op>&&|\|\||[;|]) |            # shell operators
        (?P<word>\S+)                     # regular word
        """,
        re.VERBOSE,
    )

    parts = []
    current_tokens = []

    for match in token_pattern.finditer(cmd):
        if match.group("op"):
            # Found an operator - flush current command
            if current_tokens:
                parts.append(" ".join(current_tokens))
                current_tokens = []
        else:
            # Accumulate tokens for current command
            token = match.group("dquote") or match.group("squote") or match.group("word")
            if token:
                current_tokens.append(token)

    # Don't forget the last command
    if current_tokens:
        parts.append(" ".join(current_tokens))

    return parts


def validate_path(path_str: str, project_root: Path, home_dir: Path, cmd_name: str) -> None:
    """
    Validate that a path is safe for destructive operations.

    Blocks:
    - Filesystem root "/"
    - Any .git directories
    - Paths outside project root
    - Home directory
    """
    expanded = os.path.expandvars(os.path.expanduser(path_str))
    resolved = Path(expanded).resolve()

    if resolved == Path("/"):
        block(f"{cmd_name}: targeting filesystem root")

    if ".git" in resolved.parts:
        block(f"{cmd_name}: targeting .git directory")

    # Must be within project root
    try:
        resolved.relative_to(project_root)
    except ValueError:
        if resolved == home_dir or home_dir in resolved.parents:
            block(f"{cmd_name}: targeting home directory")
        block(f"{cmd_name}: path outside project root: {resolved}")


def check_redirects(cmd: str) -> None:
    """Check for potentially dangerous output redirects."""
    # Match > or >> not inside quotes, potentially overwriting files
    # This is a simplified check - full parsing would require a shell parser
    redirect_pattern = re.compile(
        r"""
        (?<!['"]) # not preceded by quote
        >{1,2}    # > or >>
        \s*       # optional whitespace
        (/[^\s]+) # absolute path
        """,
        re.VERBOSE,
    )

    match = redirect_pattern.search(cmd)
    if match:
        target = match.group(1)
        if target.startswith("/") and not target.startswith(os.getcwd()):
            block(f"redirect to path outside cwd: {target}")


def check_shell_expansion(cmd: str) -> None:
    """Block dangerous shell expansions."""
    dangerous_patterns = [
        (r"\$\(", "command substitution $()"),
        (r"`[^`]+`", "backtick command substitution"),
        (r"\$\{[^}]*[^}]\}", "complex variable expansion"),
        (r">\s*/dev/sd", "writing to block device"),
        (r">\s*/dev/null", None),  # /dev/null is safe, don't block
    ]

    for pattern, reason in dangerous_patterns:
        if reason and re.search(pattern, cmd):
            block(f"dangerous shell expansion: {reason}")


def get_command_args(tokens: list[str]) -> list[str]:
    """Extract non-flag arguments from token list."""
    return [t for t in tokens[1:] if not t.startswith("-")]


def check_rm(tokens: list[str], project_root: Path, home_dir: Path) -> None:
    """Validate rm command usage."""
    if "--no-preserve-root" in tokens:
        block("rm: --no-preserve-root is blocked")

    flags = [t for t in tokens[1:] if t.startswith("-")]
    has_recursive = any(f in flags or "-r" in f or "-R" in f for f in flags)
    has_force = any("-f" in f for f in flags)

    args = get_command_args(tokens)
    if not args:
        block("rm: no target paths specified")

    for path_str in args:
        # Block recursive force delete patterns like /* or ./*
        if has_recursive and has_force and ("/*" in path_str or path_str in (".", "..", "*")):
            block(f"rm: dangerous pattern {path_str}")

        validate_path(path_str, project_root, home_dir, "rm")


def check_mv(tokens: list[str], project_root: Path, home_dir: Path) -> None:
    """Validate mv command - ensure both source and dest are in project."""
    args = get_command_args(tokens)
    if len(args) < 2:
        block("mv: requires source and destination")

    for path_str in args:
        validate_path(path_str, project_root, home_dir, "mv")


def check_git(tokens: list[str]) -> None:
    """Only allow read-only git commands."""
    if len(tokens) < 2:
        return  # Just "git" with no subcommand

    subcommand = tokens[1]

    # Handle git flags before subcommand (e.g., git -C /path status)
    idx = 1
    while idx < len(tokens) and tokens[idx].startswith("-"):
        idx += 1
        # Skip the argument to flags that take one
        if idx < len(tokens) and tokens[idx - 1] in ("-C", "-c", "--git-dir", "--work-tree"):
            idx += 1

    if idx >= len(tokens):
        return

    subcommand = tokens[idx]

    if subcommand not in GIT_READ_COMMANDS:
        block(f"git: non-read command '{subcommand}' is blocked")

    # Extra checks for commands that have destructive subcommands
    if subcommand == "stash" and len(tokens) > idx + 1:
        stash_action = tokens[idx + 1]
        if stash_action in ("drop", "pop", "clear", "push", "save"):
            block(f"git stash {stash_action} is blocked")

    if subcommand == "branch" and any(f in tokens for f in ("-d", "-D", "--delete")):
        block("git branch delete is blocked")

    if subcommand == "tag" and any(f in tokens for f in ("-d", "--delete")):
        block("git tag delete is blocked")

    if subcommand == "remote" and any(a in tokens for a in ("add", "remove", "rm", "rename", "set-url")):
        block("git remote modification is blocked")

    if subcommand == "config" and "--unset" in tokens:
        block("git config --unset is blocked")


def check_find(tokens: list[str]) -> None:
    """Block destructive find usage."""
    if "-delete" in tokens:
        block("find: -delete is blocked")
    if "-exec" in tokens:
        # Check what's being executed
        try:
            exec_idx = tokens.index("-exec")
            exec_cmd = tokens[exec_idx + 1] if exec_idx + 1 < len(tokens) else ""
            if exec_cmd in ("rm", "mv", "shred", "truncate"):
                block(f"find: -exec {exec_cmd} is blocked")
        except (ValueError, IndexError):
            pass


def check_tar(tokens: list[str], project_root: Path, home_dir: Path) -> None:
    """Validate tar extraction - only allow within project root."""
    # Check if extracting
    is_extract = any(
        ("-x" in t or "--extract" in t or "-xf" in t or "-xzf" in t or "-xjf" in t)
        for t in tokens
    )

    if not is_extract:
        return  # Creating archives is fine

    # Find the -C/--directory target or default to cwd
    extract_dir = None
    for i, t in enumerate(tokens):
        if t in ("-C", "--directory") and i + 1 < len(tokens):
            extract_dir = tokens[i + 1]
            break
        if t.startswith("-C"):
            extract_dir = t[2:]
            break

    if extract_dir:
        validate_path(extract_dir, project_root, home_dir, "tar")


def check_xargs(tokens: list[str]) -> None:
    """Block xargs with destructive commands."""
    destructive = {"rm", "mv", "shred", "truncate", "dd"}
    for t in tokens[1:]:
        if t in destructive:
            block(f"xargs: {t} is blocked")


def check_chmod_chown(tokens: list[str], project_root: Path, home_dir: Path) -> None:
    """Block recursive permission changes, validate paths."""
    if "-R" in tokens or "--recursive" in tokens:
        block(f"{tokens[0]}: recursive changes are blocked")

    args = get_command_args(tokens)
    # Skip the mode/owner argument
    paths = args[1:] if len(args) > 1 else []
    for p in paths:
        validate_path(p, project_root, home_dir, tokens[0])


def check_package_managers(subcmd: str, tokens: list[str]) -> None:
    """Block destructive package manager operations."""
    for pattern, blocked_actions in BLOCKED_PACKAGE_PATTERNS:
        if pattern.match(subcmd):
            for action in blocked_actions:
                if action in tokens:
                    block(f"package manager destructive action: {action}")


def main() -> None:
    payload = json.load(sys.stdin)

    tool = payload.get("tool")
    if tool != "bash":
        sys.exit(EXIT_ALLOW)

    cmd = payload.get("input", {}).get("command", "")
    cwd = payload.get("input", {}).get("cwd", os.getcwd())

    if not cmd:
        sys.exit(EXIT_ALLOW)

    project_root = Path(os.environ.get("PROJECT_ROOT", cwd)).resolve()
    home_dir = Path.home()

    # Check for dangerous redirects in the full command
    check_redirects(cmd)

    # Check for dangerous shell expansions
    check_shell_expansion(cmd)

    # Split and analyze each subcommand
    try:
        parts = split_commands(cmd)
    except Exception:
        block("failed to parse command")

    for subcmd in parts:
        subcmd = subcmd.strip()

        # Remove sudo prefix
        if subcmd.startswith("sudo "):
            subcmd = subcmd[5:].strip()

        try:
            tokens = shlex.split(subcmd)
        except ValueError:
            block("failed to tokenize subcommand")

        if not tokens:
            continue

        cmd_name = tokens[0]

        # Check for mkfs* variants
        if cmd_name.startswith("mkfs"):
            block(f"{cmd_name}: filesystem creation is blocked")

        # System-level commands
        if cmd_name in BLOCKED_SYSTEM_COMMANDS:
            block(f"{cmd_name}: dangerous system command is blocked")

        # Network commands
        if cmd_name in BLOCKED_NETWORK_COMMANDS:
            block(f"{cmd_name}: network command is blocked")

        # Specific command checks
        if cmd_name in ("rm", "unlink"):
            check_rm(tokens, project_root, home_dir)

        elif cmd_name == "mv":
            check_mv(tokens, project_root, home_dir)

        elif cmd_name == "git":
            check_git(tokens)

        elif cmd_name == "find":
            check_find(tokens)

        elif cmd_name == "tar":
            check_tar(tokens, project_root, home_dir)

        elif cmd_name == "xargs":
            check_xargs(tokens)

        elif cmd_name in ("chmod", "chown", "chgrp"):
            check_chmod_chown(tokens, project_root, home_dir)

        elif cmd_name in ("truncate", "shred"):
            args = get_command_args(tokens)
            for p in args:
                validate_path(p, project_root, home_dir, cmd_name)

        elif cmd_name == "unzip":
            # Allow unzip but validate destination
            for i, t in enumerate(tokens):
                if t == "-d" and i + 1 < len(tokens):
                    validate_path(tokens[i + 1], project_root, home_dir, "unzip")
                    break

        # Package manager checks
        check_package_managers(subcmd, tokens)

    # All checks passed
    sys.exit(EXIT_ALLOW)


if __name__ == "__main__":
    main()
