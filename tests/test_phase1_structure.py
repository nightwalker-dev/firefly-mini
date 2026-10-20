"""Comprehensive tests for Phase 1 Architectural Refactoring and Core Features."""

import asyncio

import pytest
from pydantic import BaseModel, Field

from firefly.agent.executor import ToolExecutor
from firefly.agent.planner import Planner
from firefly.agent.reflector import Reflector
from firefly.agent.tool_registry import ToolRegistry, tool
from firefly.core.config import load_config
from firefly.core.container import Container, ContainerError
from firefly.core.events import Event, EventBus
from firefly.core.lifecycle import LifecycleManager
from firefly.core.result import Err, Ok, Result, UnwrapError, run_result
from firefly.display.base import HeadlessDisplay, get_display_backend
from firefly.providers.base import LLMResponse, MockLLMProvider, ToolCall


# ==============================================================================
# Feature 11: Result[T, E] Tests
# ==============================================================================
def test_result_ok_flow():
    res: Result[int, str] = Ok(42)
    assert res.is_ok() is True
    assert res.is_err() is False
    assert res.unwrap() == 42
    assert res.unwrap_or(0) == 42

    mapped = res.map(lambda x: x * 2)
    assert mapped.unwrap() == 84

    chained = res.and_then(lambda x: Ok(str(x)))
    assert chained.unwrap() == "42"


def test_result_err_flow():
    res: Result[int, str] = Err("failure")
    assert res.is_ok() is False
    assert res.is_err() is True
    assert res.unwrap_or(99) == 99
    assert res.unwrap_err() == "failure"

    with pytest.raises(UnwrapError):
        res.unwrap()

    mapped_err = res.map_err(lambda e: f"fatal: {e}")
    assert mapped_err.unwrap_err() == "fatal: failure"


def test_run_result_helper():
    ok_res = run_result(lambda: int("123"))
    assert ok_res.is_ok()
    assert ok_res.unwrap() == 123

    err_res = run_result(lambda: int("invalid"))
    assert err_res.is_err()
    assert isinstance(err_res.unwrap_err(), ValueError)


# ==============================================================================
# Feature 5: Central Event Bus Tests
# ==============================================================================
def test_event_bus_sync_pubsub():
    bus = EventBus()
    received = []

    bus.subscribe("system.alert", lambda ev: received.append(ev.data.get("msg")))
    bus.publish_sync(Event(topic="system.alert", data={"msg": "overheating"}))

    assert received == ["overheating"]


def test_event_bus_wildcard_matching():
    bus = EventBus()
    received = []

    bus.subscribe("agent.*", lambda ev: received.append(ev.topic))
    bus.subscribe("*", lambda ev: received.append("wildcard:" + ev.topic))

    bus.publish_sync(Event(topic="agent.step"))
    bus.publish_sync(Event(topic="system.boot"))

    assert "agent.step" in received
    assert "wildcard:agent.step" in received
    assert "wildcard:system.boot" in received


@pytest.mark.asyncio
async def test_event_bus_async_dispatch():
    bus = EventBus()
    events = []

    async def async_listener(ev):
        events.append(ev.topic)

    unsub = bus.subscribe("voice.heard", async_listener)
    await bus.publish(Event(topic="voice.heard"))
    assert events == ["voice.heard"]

    unsub()
    await bus.publish(Event(topic="voice.heard"))
    assert len(events) == 1


# ==============================================================================
# Feature 6: Dependency Injection Container Tests
# ==============================================================================
def test_container_singleton_and_factory():
    c = Container()
    count = 0

    def counter_factory(_):
        nonlocal count
        count += 1
        return count

    c.register_singleton("service.counter", counter_factory)
    assert c.resolve("service.counter") == 1
    assert c.resolve("service.counter") == 1  # Same singleton

    c.register_factory("service.transient", counter_factory)
    assert c.resolve("service.transient") == 2
    assert c.resolve("service.transient") == 3


def test_container_hierarchy_overrides():
    parent = Container()
    parent.register_instance("db.name", "prod_db")

    child = parent.create_child()
    assert child.resolve("db.name") == "prod_db"

    child.register_instance("db.name", "test_db")
    assert child.resolve("db.name") == "test_db"
    assert parent.resolve("db.name") == "prod_db"


def test_container_unbound_raises():
    c = Container()
    with pytest.raises(ContainerError):
        c.resolve("missing")
    assert c.resolve_optional("missing") is None


# ==============================================================================
# Features 7, 8, 14: Layered Configuration & Validation Tests
# ==============================================================================
def test_config_env_overrides(monkeypatch):
    monkeypatch.setenv("FIREFLY_LLM_MODEL", "llama3.3:70b")
    monkeypatch.setenv("FIREFLY_SHELL_TIMEOUT", "45.0")
    monkeypatch.setenv("FIREFLY_ENABLE_VOICE", "false")

    cfg = load_config()
    assert cfg.llm.model == "llama3.3:70b"
    assert cfg.shell_timeout == 45.0
    assert cfg.features.enable_voice is False


def test_config_toml_loading(tmp_path):
    toml_file = tmp_path / "config.toml"
    toml_file.write_text("""
[llm]
model = "deepseek-coder:6.7b"
timeout = 60.0

[guardrails]
auto_approve_max_risk = 2
""")
    cfg = load_config(toml_path=toml_file)
    assert cfg.llm.model == "deepseek-coder:6.7b"
    assert cfg.llm.timeout == 60.0
    assert cfg.auto_approve_max_risk == 2


def test_config_validation_error():
    with pytest.raises(ValueError, match="Invalid Firefly configuration"):
        # Timeout must be float, invalid string triggers validation error
        load_config(cli_overrides={"llm.timeout": "not-a-number"})


# ==============================================================================
# Features 3 & 4: Tool Registry & Typed @tool Decorator Tests
# ==============================================================================
class CalculatorArgs(BaseModel):
    a: int = Field(description="First number")
    b: int = Field(description="Second number")


def test_tool_registry_and_schema():
    reg = ToolRegistry()

    @tool(name="calc_add", description="Add two integers", args_schema=CalculatorArgs, registry=reg)
    def add(a: int, b: int) -> int:
        return a + b

    t = reg.get("calc_add")
    assert t is not None
    schema = t.to_json_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "calc_add"
    assert "properties" in schema["function"]["parameters"]
    assert "a" in schema["function"]["parameters"]["properties"]


@pytest.mark.asyncio
async def test_tool_async_execution():
    reg = ToolRegistry()

    @tool(name="async_echo", registry=reg)
    async def async_echo(text: str) -> str:
        await asyncio.sleep(0.01)
        return f"echo: {text}"

    t = reg.get("async_echo")
    assert t is not None
    res = await t.execute(text="cyber-cat")
    assert res.is_ok()
    assert res.unwrap() == "echo: cyber-cat"


# ==============================================================================
# Feature 2: Planner, Executor, Reflector Tests
# ==============================================================================
def test_planner_history():
    p = Planner()
    p.add_user_message("check uptime")
    p.add_assistant_message("thinking...", tool_calls=[{"id": "c1", "name": "bash_run"}])
    p.add_tool_result("c1", "bash_run", "up 2 hours")

    msgs = p.get_messages()
    assert len(msgs) == 4
    assert msgs[1]["role"] == "user"
    assert msgs[2]["role"] == "assistant"
    assert msgs[3]["role"] == "tool"

    # Test system message injection (memory/context insertion)
    p.inject_system_message("contextual memory block", index=1)
    msgs_after = p.get_messages()
    assert len(msgs_after) == 5
    assert msgs_after[1]["role"] == "system"
    assert msgs_after[1]["content"] == "contextual memory block"


@pytest.mark.asyncio
async def test_executor_with_event_bus():
    reg = ToolRegistry()
    bus = EventBus()
    logged = []

    bus.subscribe("tool.*", lambda ev: logged.append(ev.topic))

    @tool(name="simple_test", registry=reg)
    def simple_test(val: str) -> str:
        return f"got: {val}"

    executor = ToolExecutor(registry=reg, bus=bus)
    output = await executor.execute_tool("simple_test", {"val": "123"})

    assert output == "got: 123"
    assert "tool.started" in logged
    assert "tool.finished" in logged


def test_reflector_step_evaluation():
    reflector = Reflector()
    ok_eval = reflector.evaluate_step("bash_run", '{"exit_code": 0, "stdout": "ok"}')
    assert ok_eval.is_success is True

    err_eval = reflector.evaluate_step(
        "bash_run", '{"exit_code": 1, "stderr": "permission denied"}'
    )
    assert err_eval.is_success is False
    assert "permission denied" in err_eval.feedback


# ==============================================================================
# Feature 9: LLM Providers Tests
# ==============================================================================
@pytest.mark.asyncio
async def test_mock_llm_provider():
    mock = MockLLMProvider()
    mock.enqueue(
        LLMResponse(
            content="Let me check.",
            tool_calls=[ToolCall(id="1", name="bash_run", arguments={"command": "df -h"})],
        )
    )

    res = await mock.chat([{"role": "user", "content": "disk space"}])
    assert res.is_ok()
    resp = res.unwrap()
    assert resp.content == "Let me check."
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "bash_run"


# ==============================================================================
# Feature 10: Abstract Display Backend Tests
# ==============================================================================
def test_headless_display_backend(tmp_path):
    disp = HeadlessDisplay()
    assert disp.move_mouse(250, 400).unwrap() is True
    assert disp.cursor_x == 250
    assert disp.cursor_y == 400

    assert disp.click("right").unwrap() is True
    assert "right_single" in disp.clicks

    assert disp.type_text("pwd\n").unwrap() is True
    assert "pwd\n" in disp.last_typed

    cap = disp.capture_screen(tmp_path / "shot.png")
    assert cap.is_ok()
    assert cap.unwrap().exists()


def test_get_display_backend_factory():
    disp = get_display_backend("headless")
    assert isinstance(disp, HeadlessDisplay)


# ==============================================================================
# Feature 13: Lifecycle Manager Tests
# ==============================================================================
def test_lifecycle_manager():
    bus = EventBus()
    lm = LifecycleManager(bus=bus)
    order = []

    lm.on_startup(lambda: order.append("start1"))
    lm.on_startup(lambda: order.append("start2"))
    lm.on_shutdown(lambda: order.append("stop1"))
    lm.on_shutdown(lambda: order.append("stop2"))

    lm.start()
    assert lm.is_running is True
    assert order == ["start1", "start2"]

    lm.shutdown()
    assert lm.is_running is False
    # Shutdown hooks run in reverse registration order
    assert order == ["start1", "start2", "stop2", "stop1"]
