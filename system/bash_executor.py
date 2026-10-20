"""Backward-compatibility shim for system.bash_executor -> firefly.system.bash_executor."""

from __future__ import annotations

from firefly.system.bash_executor import *  # noqa: F401, F403
from firefly.system.bash_executor import BashExecutor, ExecutionResult

__all__ = ["BashExecutor", "ExecutionResult"]
