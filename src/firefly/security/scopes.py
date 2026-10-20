"""Per-tool permission scopes and least-privilege access control (Feature 92)."""

from __future__ import annotations

from enum import Enum
from typing import Iterable, Set


class Scope(str, Enum):
    """Standard permission scopes for agent capabilities."""

    FS_READ = "fs:read"  # Read-only filesystem operations
    FS_WRITE = "fs:write"  # Creating, modifying, or deleting files
    PROC_EXEC = "proc:exec"  # Executing arbitrary subprocesses or shell commands
    NET_EGRESS = "net:egress"  # Network egress (curl, wget, APIs)
    SYS_ADMIN = "sys:admin"  # Elevated system administration (systemctl, apt, ufw)
    UI_INPUT = "ui:input"  # Synthesizing keyboard/mouse input
    MEM_READ = "mem:read"  # Querying memory store
    MEM_WRITE = "mem:write"  # Storing or wiping memory entries


# Least-privilege default scopes granted to the agent upon startup
DEFAULT_SCOPES: Set[str] = {
    Scope.FS_READ.value,
    Scope.MEM_READ.value,
}

# Full administrative scopes
ALL_SCOPES: Set[str] = {s.value for s in Scope}


class PermissionScopeError(PermissionError):
    """Raised when an operation requires a scope not granted to the current session."""

    def __init__(self, tool_name: str, missing_scopes: Iterable[str]):
        missing_str = ", ".join(sorted(missing_scopes))
        super().__init__(
            f"Permission Denied: tool '{tool_name}' requires scope(s) [{missing_str}] "
            f"which are not granted to the current session (least-privilege mode)."
        )
        self.tool_name = tool_name
        self.missing_scopes = set(missing_scopes)


class ScopeManager:
    """Manages granted security scopes for the agent session."""

    def __init__(self, initial_scopes: Iterable[str | Scope] | None = None) -> None:
        if initial_scopes is None:
            self._granted: Set[str] = set(DEFAULT_SCOPES)
        else:
            self._granted = {s.value if isinstance(s, Scope) else str(s) for s in initial_scopes}

    @property
    def granted_scopes(self) -> Set[str]:
        """Returns a copy of currently granted scopes."""
        return set(self._granted)

    def has_scope(self, scope: str | Scope) -> bool:
        """Checks if a specific scope is currently granted."""
        val = scope.value if isinstance(scope, Scope) else str(scope)
        return val in self._granted

    def check_scopes(self, tool_name: str, required_scopes: Iterable[str | Scope]) -> bool:
        """Verifies that all required scopes are granted; raises PermissionScopeError if not."""
        req_set = {s.value if isinstance(s, Scope) else str(s) for s in required_scopes}
        missing = req_set - self._granted
        if missing:
            raise PermissionScopeError(tool_name, missing)
        return True

    def grant(self, *scopes: str | Scope) -> None:
        """Grants one or more scopes to the active session."""
        for s in scopes:
            self._granted.add(s.value if isinstance(s, Scope) else str(s))

    def revoke(self, *scopes: str | Scope) -> None:
        """Revokes one or more scopes from the active session."""
        for s in scopes:
            val = s.value if isinstance(s, Scope) else str(s)
            self._granted.discard(val)

    def reset_to_defaults(self) -> None:
        """Resets granted scopes to the safe least-privilege defaults."""
        self._granted = set(DEFAULT_SCOPES)

    def grant_all(self) -> None:
        """Grants all defined scopes."""
        self._granted = set(ALL_SCOPES)


# Global default scope manager
default_scope_manager = ScopeManager()
