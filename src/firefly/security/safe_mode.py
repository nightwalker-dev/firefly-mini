"""Safe-mode controller: enforces strictly read-only system inspection (Feature 103)."""

from __future__ import annotations

import re
from typing import Set, Tuple


class SafeModeViolation(PermissionError):
    """Raised when an operation attempts state modification while Safe Mode is engaged."""

    def __init__(self, action_name: str, reason: str):
        super().__init__(
            f"Safe Mode Violation: cannot execute modifying action '{action_name}'. {reason}"
        )
        self.action_name = action_name
        self.reason = reason


class SafeModeController:
    """Restricts agent capabilities to strictly read-only passive inspection."""

    # Allowed read-only inspection binaries and utilities
    ALLOWED_INSPECTION_COMMANDS: Set[str] = {
        "ls",
        "dir",
        "cat",
        "head",
        "tail",
        "more",
        "less",
        "grep",
        "egrep",
        "fgrep",
        "find",
        "stat",
        "file",
        "uname",
        "uptime",
        "whoami",
        "id",
        "date",
        "cal",
        "df",
        "du",
        "free",
        "ps",
        "top",
        "htop",
        "ss",
        "netstat",
        "ip",
        "ifconfig",
        "journalctl",
        "dmesg",
        "env",
        "printenv",
        "which",
        "whereis",
        "type",
        "echo",
        "printf",
        "wc",
        "diff",
        "cmp",
        "tree",
        "pytest",
        "ruff",
        "mypy",
    }

    # Prohibited modifying verbs & syntax
    MUTATING_PATTERNS = [
        re.compile(r">"),  # File redirection output (> or >>)
        re.compile(
            r"\b(?:rm|mv|cp|touch|mkdir|rmdir|chmod|chown|chgrp|truncate|shred|dd)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(?:apt|apt-get|dnf|yum|pacman|pip|npm|cargo)\b", re.IGNORECASE),
        re.compile(
            r"\b(?:systemctl|service|kill|killall|pkill|reboot|shutdown|poweroff)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(?:sed\s+-i|perl\s+-i|python\s+-c\s+.*open\(.*['\"][wa])", re.IGNORECASE),
        re.compile(r"\bgit\s+(?:commit|push|checkout\s+-b|reset|rebase|merge|stash)\b"),
    ]

    def __init__(self, enabled: bool = False) -> None:
        self._enabled = enabled

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        self._enabled = False

    def evaluate_command(self, command: str) -> Tuple[bool, str]:
        """Verifies that the shell command is passive and performs zero state changes.

        Returns (allowed: bool, reason: str).
        """
        if not self._enabled:
            return True, "Safe mode disabled."

        cmd_clean = command.strip()

        # Check for mutation syntax (redirections, deletions, installations)
        for pattern in self.MUTATING_PATTERNS:
            if pattern.search(cmd_clean):
                return (
                    False,
                    "Safe Mode is active (read-only inspection only). "
                    f"Modifying syntax pattern '{pattern.pattern}' is forbidden.",
                )

        # Inspect binary invoked (first word)
        first_token = cmd_clean.split()[0].split("/")[-1] if cmd_clean else ""
        if first_token not in self.ALLOWED_INSPECTION_COMMANDS:
            return (
                False,
                f"Command '{first_token}' is not in the safe read-only inspection whitelist.",
            )

        return True, "Command permitted in safe read-only mode."

    def evaluate_tool(self, tool_name: str, scopes: list[str]) -> Tuple[bool, str]:
        """Ensures that invoked tool does not mutate state when safe mode is active."""
        if not self._enabled:
            return True, "Safe mode disabled."

        forbidden_scopes = {"fs:write", "sys:admin", "ui:input", "mem:write"}
        found_forbidden = set(scopes) & forbidden_scopes
        if found_forbidden:
            return (
                False,
                f"Tool '{tool_name}' requires mutating scope(s) {sorted(found_forbidden)}, "
                "which are prohibited in Safe Mode.",
            )

        return True, "Tool permitted in safe mode."


# Global default safe-mode controller
default_safe_mode = SafeModeController()
