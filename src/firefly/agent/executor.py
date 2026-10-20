"""Tool Executor: executes agent actions with event publishing, scope enforcement, and Result unwrapping."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from firefly.agent.tool_registry import ToolRegistry, default_registry
from firefly.core.events import Event, EventBus, default_bus
from firefly.core.result import Result
from firefly.security.provenance import default_provenance
from firefly.security.safe_mode import SafeModeController, default_safe_mode
from firefly.security.scopes import PermissionScopeError, ScopeManager, default_scope_manager


class ToolExecutor:
    """Executes validated tool actions with permission scoping and event reporting."""

    def __init__(
        self,
        registry: ToolRegistry = default_registry,
        bus: EventBus = default_bus,
        scope_manager: Optional[ScopeManager] = None,
        safe_mode: Optional[SafeModeController] = None,
    ) -> None:
        self.registry = registry
        self.bus = bus
        self.scope_manager: ScopeManager = scope_manager or default_scope_manager
        self.safe_mode: SafeModeController = safe_mode or default_safe_mode

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> str:
        """Looks up tool in registry, enforces scopes and safe mode, dispatches, and returns response."""
        start = time.time()
        prov = default_provenance.get_current()
        prov_dict = prov.to_dict() if prov else None

        await self.bus.publish(
            Event(
                topic="tool.started",
                data={"tool": name, "args": args, "provenance": prov_dict},
            )
        )

        tool_obj = self.registry.get(name)
        if not tool_obj:
            err_msg = json.dumps({"error": f"Tool '{name}' not found in registry"})
            await self.bus.publish(
                Event(topic="tool.finished", data={"tool": name, "error": err_msg})
            )
            return err_msg

        # Feature 103: Safe Mode evaluation
        tool_scopes: list[str] = getattr(tool_obj, "scopes", None) or []
        allowed_sm, sm_reason = self.safe_mode.evaluate_tool(name, tool_scopes)
        if not allowed_sm:
            err_msg = json.dumps({"error": f"Safe Mode Violation: {sm_reason}"})
            await self.bus.publish(
                Event(topic="tool.finished", data={"tool": name, "error": err_msg})
            )
            return err_msg

        # Feature 92: Per-tool permission scopes check
        try:
            self.scope_manager.check_scopes(name, tool_scopes)
        except PermissionScopeError as scope_err:
            err_msg = json.dumps({"error": str(scope_err)})
            await self.bus.publish(
                Event(topic="tool.finished", data={"tool": name, "error": err_msg})
            )
            return err_msg

        res: Result[str, Exception] = await tool_obj.execute(**args)
        duration_ms = (time.time() - start) * 1000

        if res.is_ok():
            output = res.unwrap()
            await self.bus.publish(
                Event(
                    topic="tool.finished",
                    data={
                        "tool": name,
                        "success": True,
                        "output": output[:200],
                        "duration_ms": duration_ms,
                        "provenance": prov_dict,
                    },
                )
            )
            return output
        else:
            err_str = json.dumps({"error": str(res.unwrap_err())})
            await self.bus.publish(
                Event(
                    topic="tool.finished",
                    data={
                        "tool": name,
                        "success": False,
                        "error": err_str,
                        "duration_ms": duration_ms,
                        "provenance": prov_dict,
                    },
                )
            )
            return err_str
