"""Firefly Mini — Autonomous Cyber-Cat Linux Agent."""

from __future__ import annotations

from firefly.agent.agent import FireflyAgent
from firefly.core.config import settings
from firefly.core.events import Event, EventBus, default_bus
from firefly.core.guardrails import Action, Guardrails, Risk, Verdict
from firefly.core.result import Err, Ok, Result
from firefly.system.bash_executor import BashExecutor

__version__ = "2.1.0"
__all__ = [
    "FireflyAgent",
    "settings",
    "Guardrails",
    "BashExecutor",
    "Event",
    "EventBus",
    "default_bus",
    "Result",
    "Ok",
    "Err",
    "Action",
    "Risk",
    "Verdict",
]
