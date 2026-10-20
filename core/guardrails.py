"""Backward-compatibility shim for core.guardrails -> firefly.core.guardrails."""

from __future__ import annotations

from firefly.core.guardrails import *  # noqa: F401, F403
from firefly.core.guardrails import (
    Action,
    Challenge,
    Finding,
    Guardrails,
    GuardrailViolation,
    ImpactReport,
    KillSwitch,
    MFAGate,
    RateLimiter,
    Risk,
    Verdict,
    split_segments,
)

__all__ = [
    "Action",
    "Challenge",
    "Finding",
    "Guardrails",
    "GuardrailViolation",
    "ImpactReport",
    "KillSwitch",
    "MFAGate",
    "RateLimiter",
    "Risk",
    "Verdict",
    "split_segments",
]
