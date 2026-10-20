"""Plugin-driven Tool Registry with Pydantic typed schemas and auto-generated JSON specifications."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

from pydantic import BaseModel, create_model

from firefly.core.result import Err, Ok, Result


@dataclass
class Tool:
    """Registered tool metadata and execution handler."""

    name: str
    description: str
    handler: Callable[..., Any]
    args_schema: Type[BaseModel]
    is_async: bool = False
    scopes: List[str] = field(default_factory=list)

    def to_json_schema(self) -> Dict[str, Any]:
        """Auto-generates OpenAI/Ollama compatible function definition."""
        schema = self.args_schema.model_json_schema()
        # Clean up internal pydantic metadata titles
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

    async def execute(self, **kwargs: Any) -> Result[str, Exception]:
        """Validates arguments through Pydantic and executes the handler."""
        try:
            validated = self.args_schema(**kwargs)
            call_args = validated.model_dump()
            if self.is_async:
                res = await self.handler(**call_args)
            else:
                loop = asyncio.get_running_loop()
                res = await loop.run_in_executor(None, lambda: self.handler(**call_args))
            return Ok(str(res))
        except Exception as exc:
            return Err(exc)


class ToolRegistry:
    """Central registry and dynamic discovery engine for tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}

    def register(
        self,
        name: str,
        description: str,
        handler: Callable[..., Any],
        args_schema: Optional[Type[BaseModel]] = None,
        scopes: Optional[List[str]] = None,
    ) -> Tool:
        """Registers a tool with an explicit or dynamically inferred Pydantic model and permission scopes."""
        if args_schema is None:
            # Dynamically infer Pydantic model from function type signatures
            sig = inspect.signature(handler)
            fields: Dict[str, Any] = {}
            for param in sig.parameters.values():
                if param.name in ("self", "cls"):
                    continue
                type_hint = param.annotation if param.annotation != inspect.Parameter.empty else Any
                default_val = param.default if param.default != inspect.Parameter.empty else ...
                fields[param.name] = (type_hint, default_val)
            args_schema = create_model(f"{name.capitalize()}Args", **fields)

        is_async = inspect.iscoroutinefunction(handler)
        t = Tool(
            name=name,
            description=description,
            handler=handler,
            args_schema=args_schema,
            is_async=is_async,
            scopes=scopes or ["fs:read"],
        )
        self._tools[name] = t
        return t

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_tools(self) -> List[Tool]:
        return list(self._tools.values())

    def get_definitions(self) -> List[Dict[str, Any]]:
        """Returns JSON schema definitions for all registered tools."""
        return [t.to_json_schema() for t in self._tools.values()]

    def discover_plugins(self, search_paths: Optional[List[Path]] = None) -> int:
        """Auto-discovers and imports Python plugin modules defining @tool annotations."""
        count = 0
        paths = search_paths or [Path("plugins")]
        for p in paths:
            if not p.is_dir():
                continue
            for file_path in p.glob("*.py"):
                if file_path.name.startswith("__"):
                    continue
                module_name = f"plugins.{file_path.stem}"
                try:
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        count += 1
                except Exception:
                    pass
        return count


default_registry = ToolRegistry()


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    args_schema: Optional[Type[BaseModel]] = None,
    scopes: Optional[List[str]] = None,
    registry: ToolRegistry = default_registry,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator to mark a function as an agent tool and register it."""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or fn.__name__
        tool_desc = description or (fn.__doc__ or "").strip().split("\n")[0] or tool_name
        registry.register(tool_name, tool_desc, fn, args_schema, scopes=scopes)
        return fn

    return decorator
