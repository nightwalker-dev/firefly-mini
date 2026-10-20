"""Backward-compatibility shim for core.agent -> firefly.agent."""

from __future__ import annotations

from firefly.agent.agent import FireflyAgent
from firefly.agent.executor import ToolExecutor
from firefly.agent.planner import SYSTEM_PERSONA, Planner
from firefly.agent.planner import SYSTEM_PERSONA as SYSTEM_PROMPT
from firefly.agent.reflector import Reflector
from firefly.agent.tool_registry import Tool, ToolRegistry, default_registry

__all__ = [
    "FireflyAgent",
    "SYSTEM_PROMPT",
    "SYSTEM_PERSONA",
    "Planner",
    "ToolExecutor",
    "Reflector",
    "ToolRegistry",
    "Tool",
    "default_registry",
]
