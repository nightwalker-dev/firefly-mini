"""Backward-compatibility shim for core.logger -> firefly.core.logger."""

from __future__ import annotations

from firefly.core.logger import *  # noqa: F401, F403
from firefly.core.logger import AuditLogger, AuditRecord, CheckpointManager

__all__ = ["AuditLogger", "AuditRecord", "CheckpointManager"]
