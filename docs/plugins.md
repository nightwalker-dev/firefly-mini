# Plugin Development Guide

Firefly Mini features an extensible, type-safe plugin system. Custom tools can be authored in simple Python scripts, automatically registered with Pydantic validation schemas, assigned granular permission scopes, and discovered at startup.

---

## 1. Architecture Overview

Every Firefly tool is wrapped in a `Tool` container that manages:
1. **Pydantic Validation**: Input arguments are strictly validated before invocation.
2. **Auto Schema Generation**: JSON schemas compliant with OpenAI/Ollama function calling are synthesized dynamically.
3. **Execution Isolation**: Sync handlers are safely scheduled onto background executors, while async handlers are awaited directly without blocking the event loop.
4. **Scope Control**: Guardrails inspect declared permission scopes (e.g., `fs:read`, `terminal:exec`, `network:fetch`) prior to execution.

---

## 2. Creating a Custom Plugin

Place your plugin script in the `plugins/` directory (e.g., `plugins/weather.py`):

```python
"""Weather lookup plugin for Firefly Mini."""

from pydantic import BaseModel, Field
from firefly.agent.tool_registry import tool


class WeatherArgs(BaseModel):
    city: str = Field(description="Name of the city to query")
    units: str = Field(default="celsius", description="Temperature unit ('celsius' or 'fahrenheit')")


@tool(
    name="get_weather",
    description="Fetch current temperature and atmospheric conditions for a target city.",
    args_schema=WeatherArgs,
    scopes=["network:fetch"],
)
async def get_weather(city: str, units: str = "celsius") -> str:
    """Queries external weather forecast API."""
    # Custom business logic or API call here
    return f"Weather in {city}: 21° {units.capitalize()}, Clear skies."
```

---

## 3. Decorator Options

The `@tool` decorator accepts the following parameters:

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `name` | `str \| None` | Function name | The unique tool identifier exposed to the LLM. |
| `description` | `str \| None` | Docstring first line | Detailed explanation of what the tool accomplishes. |
| `args_schema` | `Type[BaseModel] \| None` | Inferred dynamically | Explicit Pydantic class defining fields, types, and constraints. |
| `scopes` | `List[str] \| None` | `["fs:read"]` | Security permission scopes required to execute this tool. |
| `registry` | `ToolRegistry` | `default_registry` | Target registry instance to register the tool within. |

---

## 4. Inferred Schemas

If `args_schema` is omitted, Firefly automatically analyzes your function's Python type hints and default values to construct a Pydantic model at runtime:

```python
from firefly.agent.tool_registry import tool

@tool(scopes=["system:query"])
def uptime_check(verbose: bool = False) -> str:
    """Returns system uptime status."""
    return "Host uptime: 42 days, 3 hours"
```

---

## 5. Plugin Discovery & Lifecycle

When the Firefly Agent initializes:
1. It loads built-in tools (`read_file`, `write_file`, `list_directory`, `execute_bash`, `http_request`, `take_screenshot`).
2. It executes `registry.discover_plugins()` scanning the `plugins/` folder for any `*.py` files (ignoring files prefixed with `__`).
3. Each discovered module is imported and its `@tool` instances are registered.
4. Tool JSON schemas are attached to LLM system prompts for tool calling.
