"""Comprehensive test suite for Phase 7: DX, Testing, Observability & Packaging (Features 106 to 120)."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import firefly
from firefly.cli import app
from firefly.observability.json_logger import (
    JSONFormatter,
    StructuredLogger,
    configure_json_logging,
    get_json_logger,
)
from firefly.observability.metrics import MetricsCollector, default_metrics
from firefly.observability.tracing import Tracer, TraceSpan
from firefly.testing.mocks import MockDesktop, MockLLM
from firefly.testing.recorder import RecordedEvent, SessionPlayer, SessionRecorder

runner = CliRunner()


# ==============================================================================
# Feature 106: Structured JSON Logging with Levels, Rotation & Redaction
# ==============================================================================
def test_json_formatter_structure():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="firefly.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="Agent initialized successfully",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["level"] == "INFO"
    assert data["logger"] == "firefly.test"
    assert data["message"] == "Agent initialized successfully"
    assert data["line"] == 42
    assert "timestamp" in data
    assert "pid" in data


def test_json_formatter_secret_redaction():
    formatter = JSONFormatter()
    raw_secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    record = logging.LogRecord(
        name="firefly.sec",
        level=logging.WARNING,
        pathname=__file__,
        lineno=100,
        msg=f"Leaked token detected: {raw_secret}",
        args=(),
        exc_info=None,
    )
    record.api_key = "sk-ant-api03-abcdefghijklmno1234567890abcdef"
    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert raw_secret not in formatted
    assert "[REDACTED" in data["message"]
    assert "api_key" in data.get("extra", {})
    assert "[REDACTED" in data["extra"]["api_key"]


def test_json_formatter_exception_logging():
    formatter = JSONFormatter()
    try:
        raise ValueError("Diagnostic system failure")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="firefly.err",
        level=logging.ERROR,
        pathname=__file__,
        lineno=150,
        msg="Error encountered during execution",
        args=(),
        exc_info=exc_info,
    )
    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert "exception" in data
    assert "ValueError: Diagnostic system failure" in data["exception"]


def test_configure_json_logging(tmp_path: Path):
    log_file = tmp_path / "test_firefly.json.log"
    handler = configure_json_logging(log_file=log_file, level=logging.DEBUG)

    test_logger = logging.getLogger("firefly")
    test_logger.info("Configuration test event")
    handler.flush()

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "Configuration test event" in content


def test_structured_logger_levels():
    mock_base = logging.getLogger("test_structured")
    mock_base.setLevel(logging.DEBUG)
    s_logger = StructuredLogger(mock_base)

    # Validate that calls do not throw and accept extra kwargs
    s_logger.debug("Debug message", task_id="t1")
    s_logger.info("Info message", task_id="t2")
    s_logger.warning("Warning message", task_id="t3")
    s_logger.error("Error message", task_id="t4")
    s_logger.critical("Critical message", task_id="t5")

    direct_logger = get_json_logger("firefly.direct")
    assert isinstance(direct_logger, StructuredLogger)


# ==============================================================================
# Feature 107: System Metrics Collector
# ==============================================================================
def test_metrics_collector_record_task(tmp_path: Path):
    metrics_file = tmp_path / "metrics.json"
    collector = MetricsCollector(metrics_file=metrics_file)

    collector.record_task(success=True, duration_ms=120.5, retries=0)
    collector.record_task(success=True, duration_ms=250.0, retries=1)
    collector.record_task(success=False, duration_ms=400.0, retries=2)

    summary = collector.get_summary()
    assert summary.total_tasks == 3
    assert summary.successful_tasks == 2
    assert summary.failed_tasks == 1
    assert round(summary.success_rate, 1) == 66.7
    assert summary.total_retries == 3
    assert summary.avg_latency_ms > 0


def test_metrics_collector_latency_p95(tmp_path: Path):
    metrics_file = tmp_path / "metrics_p95.json"
    collector = MetricsCollector(metrics_file=metrics_file)

    # 100 requests with latencies 1ms to 100ms
    for i in range(1, 101):
        collector.record_task(success=True, duration_ms=float(i))

    summary = collector.get_summary()
    # 95th percentile index is 95 -> latency 96
    assert summary.p95_latency_ms == pytest.approx(96.0, abs=1.0)


def test_metrics_collector_tool_reliability(tmp_path: Path):
    metrics_file = tmp_path / "metrics_tools.json"
    collector = MetricsCollector(metrics_file=metrics_file)

    collector.record_tool_call(tool="bash", success=True, duration_ms=50.0)
    collector.record_tool_call(tool="bash", success=True, duration_ms=70.0)
    collector.record_tool_call(tool="bash", success=False, duration_ms=30.0)
    collector.record_tool_call(tool="read_file", success=True, duration_ms=10.0)

    summary = collector.get_summary()
    assert "bash" in summary.tool_reliability
    assert summary.tool_reliability["bash"]["calls"] == 3
    assert summary.tool_reliability["bash"]["successes"] == 2
    assert summary.tool_reliability["bash"]["failures"] == 1
    assert summary.tool_reliability["bash"]["success_rate"] == 66.7
    assert summary.tool_reliability["read_file"]["success_rate"] == 100.0


def test_metrics_collector_guardrail_actions(tmp_path: Path):
    metrics_file = tmp_path / "metrics_gr.json"
    collector = MetricsCollector(metrics_file=metrics_file)

    collector.record_guardrail_action("allow")
    collector.record_guardrail_action("allow")
    collector.record_guardrail_action("confirm")
    collector.record_guardrail_action("mfa")
    collector.record_guardrail_action("block")

    summary = collector.get_summary()
    assert summary.guardrail_actions["allow"] == 2
    assert summary.guardrail_actions["confirm"] == 1
    assert summary.guardrail_actions["mfa"] == 1
    assert summary.guardrail_actions["block"] == 1


def test_metrics_persistence_and_reset(tmp_path: Path):
    metrics_file = tmp_path / "metrics_persist.json"
    c1 = MetricsCollector(metrics_file=metrics_file)
    c1.record_task(success=True, duration_ms=100.0)
    assert metrics_file.exists()

    c2 = MetricsCollector(metrics_file=metrics_file)
    assert c2.get_summary().total_tasks == 1

    c2.reset()
    assert c2.get_summary().total_tasks == 0
    assert not metrics_file.exists()


# ==============================================================================
# Feature 108: CLI Metrics Dashboard (firefly stats)
# ==============================================================================
def test_cli_stats_dashboard():
    # Seed default metrics with sample data
    default_metrics.record_task(success=True, duration_ms=85.0)
    default_metrics.record_tool_call(tool="execute_bash", success=True, duration_ms=45.0)
    default_metrics.record_guardrail_action("allow")

    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "Operational Telemetry" in result.output
    assert "Tool Reliability" in result.output
    assert "Guardrail Enforcement Posture" in result.output


# ==============================================================================
# Feature 109: Distributed Execution Tracing with Waterfall Timelines
# ==============================================================================
def test_trace_span_lifecycle():
    span = TraceSpan(
        trace_id="trc_001",
        span_id="spn_001",
        parent_span_id=None,
        name="RootOperation",
        start_time=100.0,
    )
    span.add_event("cache_hit", {"key": "sys_info"})
    span.end(status="OK")

    assert span.status == "OK"
    assert span.end_time is not None
    assert len(span.events) == 1
    assert span.events[0]["name"] == "cache_hit"


def test_tracer_context_manager_and_nesting():
    tracer = Tracer()
    with tracer.start_span("agent_turn") as root_span:
        assert tracer.get_current_span() == root_span
        with tracer.start_span("tool_call") as child_span:
            assert child_span.parent_span_id == root_span.span_id
            assert child_span.trace_id == root_span.trace_id

    spans = tracer.get_spans()
    assert len(spans) == 2
    # Child exits before root
    assert spans[0].name == "tool_call"
    assert spans[1].name == "agent_turn"


def test_tracer_record_step():
    tracer = Tracer()
    secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    span = tracer.record_step(
        step_idx=1,
        thought=f"I must check authorization {secret}",
        action="execute_bash(whoami)",
        observation="root",
        duration_ms=45.2,
    )
    assert span.name == "ReAct.Step_1"
    assert secret not in span.attributes["thought"]
    assert "[REDACTED" in span.attributes["thought"]


def test_tracer_waterfall_format():
    tracer = Tracer()
    tracer.record_step(
        step_idx=1,
        thought="Thinking about file search",
        action="find_files",
        observation="file1.txt",
        duration_ms=65.0,
    )
    waterfall = tracer.format_waterfall()
    assert "Firefly Execution Trace Waterfall" in waterfall
    assert "ReAct.Step_1" in waterfall
    assert "thought:" in waterfall


def test_tracer_clear():
    tracer = Tracer()
    tracer.record_step(1, "t", "a", "o", 10.0)
    assert len(tracer.get_spans()) == 1
    tracer.clear()
    assert len(tracer.get_spans()) == 0
    assert "No trace spans recorded." in tracer.format_waterfall()


# ==============================================================================
# Feature 110: Custom Pytest Marker Categorization
# ==============================================================================
def test_pytest_markers_registered():
    pyproject_path = Path("pyproject.toml")
    assert pyproject_path.exists()
    content = pyproject_path.read_text(encoding="utf-8")

    assert "markers = [" in content
    assert '"unit:' in content
    assert '"integration:' in content
    assert '"adversarial:' in content
    assert '"slow:' in content


# ==============================================================================
# Feature 111: Multi-Version GitHub Actions CI
# ==============================================================================
def test_github_actions_ci_matrix():
    ci_path = Path(".github/workflows/ci.yml")
    assert ci_path.exists()
    ci_data = yaml.safe_load(ci_path.read_text(encoding="utf-8"))

    assert "jobs" in ci_data
    build_job = ci_data["jobs"]["test"]
    matrix = build_job["strategy"]["matrix"]
    python_versions = matrix["python-version"]

    assert "3.10" in python_versions
    assert "3.11" in python_versions
    assert "3.12" in python_versions
    assert "3.13" in python_versions


# ==============================================================================
# Feature 112: Git Pre-Commit Hooks & Secret Scanner
# ==============================================================================
def test_pre_commit_config_validity():
    pc_path = Path(".pre-commit-config.yaml")
    assert pc_path.exists()
    pc_data = yaml.safe_load(pc_path.read_text(encoding="utf-8"))

    repos = pc_data.get("repos", [])
    repo_urls = [r.get("repo") for r in repos]
    assert any("ruff" in str(u) for u in repo_urls)
    assert any("mypy" in str(u) for u in repo_urls)

    # Check local secret scanner hook
    local_repo = next(r for r in repos if r.get("repo") == "local")
    hook_ids = [h["id"] for h in local_repo["hooks"]]
    assert "firefly-secret-scan" in hook_ids


def test_pre_commit_secret_patterns():
    # Direct validation of secret regex logic
    import re

    secret_pattern = re.compile(
        r"(ghp_[A-Za-z0-9]{36}|sk-ant-[A-Za-z0-9\-_]{32,}|AKIA[0-9A-Z]{16})"
    )
    assert secret_pattern.search("ghp_1234567890abcdefghijklmnopqrstuvwxyz")
    assert secret_pattern.search("AKIAIOSFODNN7EXAMPLE")
    assert not secret_pattern.search("ordinary harmless configuration string")


# ==============================================================================
# Feature 113: Simulation Mocks (MockLLM & MockDesktop)
# ==============================================================================
@pytest.mark.asyncio
async def test_mock_llm_queue_and_canned():
    mock = MockLLM(canned_responses=["First answer", "Second answer"])
    res1 = (await mock.chat([])).unwrap()
    assert res1.content == "First answer"

    res2 = (await mock.chat([])).unwrap()
    assert res2.content == "Second answer"

    # Fallback response
    res3 = (await mock.chat([])).unwrap()
    assert res3.content is not None
    assert "Default mock response" in res3.content


@pytest.mark.asyncio
async def test_mock_llm_tool_calls_generation():
    mock = MockLLM()
    mock.queue_response(
        response="I am reading your file",
        tool_calls=[("read_file", {"path": "/tmp/test.txt"})],
    )
    res = (await mock.chat([])).unwrap()
    assert res.content == "I am reading your file"
    assert len(res.tool_calls) == 1
    assert res.tool_calls[0].name == "read_file"
    assert res.tool_calls[0].arguments["path"] == "/tmp/test.txt"


@pytest.mark.asyncio
async def test_mock_llm_history_and_last_message():
    mock = MockLLM()
    await mock.chat([{"role": "user", "content": "How is the weather?"}])
    assert mock.call_count == 1
    assert mock.last_message_content() == "How is the weather?"


def test_mock_desktop_mouse_operations():
    desktop = MockDesktop(width=1920, height=1080)
    assert desktop.get_cursor_position() == (960, 540)

    desktop.move_cursor(100, 200)
    assert desktop.get_cursor_position() == (100, 200)

    # Clamping out-of-bounds cursor
    desktop.move_cursor(5000, -10)
    assert desktop.get_cursor_position() == (1920, 0)

    desktop.click(button="right", double=True)
    assert len(desktop.mouse_events) == 3
    assert desktop.mouse_events[-1]["button"] == "right"
    assert desktop.mouse_events[-1]["double"] is True


def test_mock_desktop_keyboard_operations():
    desktop = MockDesktop()
    desktop.type_text("ls -la\n")
    desktop.press_hotkey(["ctrl", "c"])

    assert len(desktop.keyboard_events) == 2
    assert desktop.keyboard_events[0]["text"] == "ls -la\n"
    assert desktop.keyboard_events[1]["keys"] == ["ctrl", "c"]


def test_mock_desktop_screenshot_generation(tmp_path: Path):
    desktop = MockDesktop(width=800, height=600)
    desktop.move_cursor(400, 300)
    out_file = tmp_path / "screen.png"

    img = desktop.take_screenshot(target_path=str(out_file))
    assert img.size == (800, 600)
    assert img.mode == "RGB"
    assert out_file.exists()
    assert out_file.stat().st_size > 0


# ==============================================================================
# Feature 114: Deterministic Session Recorder & Player
# ==============================================================================
def test_session_recorder_event_capture():
    recorder = SessionRecorder(session_id="rec_unit_01")
    secret = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"

    e1 = recorder.record("user_input", {"prompt": f"Search for {secret}"})
    e2 = recorder.record("tool_call", {"tool": "grep_search", "pattern": "key"})

    assert e1.index == 0
    assert e2.kind == "tool_call"
    assert secret not in e1.data["prompt"]
    assert "[REDACTED" in e1.data["prompt"]
    assert len(recorder.recording.events) == 2


def test_session_recorder_save_and_load(tmp_path: Path):
    rec_file = tmp_path / "session_test.json"
    recorder = SessionRecorder(session_id="rec_save_load")
    recorder.record("user_input", {"prompt": "Hello cat"})
    recorder.record("tool_call", {"tool": "purr"})
    recorder.save(rec_file)

    loaded = SessionRecorder.load(rec_file)
    assert loaded.session_id == "rec_save_load"
    assert len(loaded.events) == 2
    assert loaded.events[1].data["tool"] == "purr"


def test_session_player_conformance_success():
    recorder = SessionRecorder()
    recorder.record("user_input", {"prompt": "list dir"})
    recorder.record("tool_call", {"tool": "list_directory"})
    recorder.record("agent_output", {"response": "Files listed"})

    player = SessionPlayer(baseline=recorder.recording)
    actual_events = [
        RecordedEvent(index=0, timestamp=1.0, kind="tool_call", data={"tool": "list_directory"}),
        RecordedEvent(
            index=1, timestamp=2.0, kind="agent_output", data={"response": "Files listed"}
        ),
    ]

    is_conform, errors = player.verify_against(actual_events)
    assert is_conform is True
    assert len(errors) == 0


def test_session_player_discrepancy_detection():
    recorder = SessionRecorder()
    recorder.record("tool_call", {"tool": "list_directory"})

    player = SessionPlayer(baseline=recorder.recording)
    divergent_events = [
        RecordedEvent(index=0, timestamp=1.0, kind="tool_call", data={"tool": "execute_bash"}),
    ]

    is_conform, errors = player.verify_against(divergent_events)
    assert is_conform is False
    assert any("tool mismatch" in err for err in errors)


# ==============================================================================
# Feature 115: Shell Tab-Completion CLI Command
# ==============================================================================
def test_cli_completion_bash():
    result = runner.invoke(app, ["completion", "bash"])
    assert result.exit_code == 0
    assert "_FIREFLY_COMPLETE=bash_source" in result.output


def test_cli_completion_zsh():
    result = runner.invoke(app, ["completion", "zsh"])
    assert result.exit_code == 0
    assert "_FIREFLY_COMPLETE=zsh_source" in result.output


def test_cli_completion_fish():
    result = runner.invoke(app, ["completion", "fish"])
    assert result.exit_code == 0
    assert "_FIREFLY_COMPLETE=fish_source" in result.output


def test_cli_completion_unsupported():
    result = runner.invoke(app, ["completion", "powershell"])
    assert result.exit_code == 0
    assert "Unsupported shell" in result.output


# ==============================================================================
# Feature 116: Systemd Daemon Service Unit & CLI Management
# ==============================================================================
def test_systemd_service_file_validity():
    svc_file = Path("systemd/firefly-mini.service")
    assert svc_file.exists()
    content = svc_file.read_text(encoding="utf-8")

    assert "[Unit]" in content
    assert "[Service]" in content
    assert "[Install]" in content
    assert "WantedBy=default.target" in content


def test_cli_service_install_and_status(tmp_path: Path):
    result = runner.invoke(app, ["service", "install", "--dir", str(tmp_path)])
    assert result.exit_code == 0
    assert (tmp_path / "firefly-mini.service").exists()

    status_result = runner.invoke(app, ["service", "status"])
    assert status_result.exit_code == 0


# ==============================================================================
# Feature 117: Setup Script (setup.sh) Validation
# ==============================================================================
def test_setup_script_help_flag():
    result = subprocess.run(
        ["./setup.sh", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Usage: ./setup.sh" in result.stdout
    assert "--dry-run" in result.stdout


def test_setup_script_dry_run_flag():
    result = subprocess.run(
        ["./setup.sh", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "DRY-RUN MODE" in result.stdout


# ==============================================================================
# Feature 118: Containerized Environments (Dockerfile & Devcontainer)
# ==============================================================================
def test_dockerfile_layers_and_structure():
    df_path = Path("Dockerfile")
    assert df_path.exists()
    content = df_path.read_text(encoding="utf-8")

    assert "FROM python:" in content
    assert "WORKDIR /home/firefly/app" in content
    assert "pip install" in content
    assert 'CMD ["firefly", "status"]' in content


def test_devcontainer_configuration():
    dc_path = Path(".devcontainer/devcontainer.json")
    assert dc_path.exists()
    dc_data = json.loads(dc_path.read_text(encoding="utf-8"))

    assert dc_data["name"] == "Firefly Mini Development Container"
    assert dc_data["build"]["dockerfile"] == "../Dockerfile"
    assert "customizations" in dc_data
    assert "vscode" in dc_data["customizations"]


# ==============================================================================
# Feature 119: Semantic Versioning & CHANGELOG Integrity
# ==============================================================================
def test_version_alignment():
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "2.1.0"' in pyproject
    assert firefly.__version__ == "2.1.0"

    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [2.1.0]" in changelog


def test_changelog_keep_a_changelog_format():
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    assert "Keep a Changelog" in changelog
    assert "Semantic Versioning" in changelog
    assert "### Added" in changelog


# ==============================================================================
# Feature 120: MkDocs Site Documentation Structure
# ==============================================================================
def test_mkdocs_site_structure():
    mkdocs_path = Path("mkdocs.yml")
    assert mkdocs_path.exists()
    yaml.SafeLoader.add_constructor(
        "tag:yaml.org,2002:python/name:pymdownx.superfences.fence_code_format",
        lambda loader, node: "",
    )
    config = yaml.safe_load(mkdocs_path.read_text(encoding="utf-8"))

    assert config["site_name"] == "Firefly Mini Documentation"
    assert "nav" in config

    # Check each file declared in nav exists
    for item in config["nav"]:
        for title, rel_path in item.items():
            doc_file = Path("docs") / rel_path
            assert doc_file.exists(), f"Nav page missing: {doc_file}"


def test_markdown_documentation_integrity():
    docs_dir = Path("docs")
    for doc in docs_dir.glob("*.md"):
        content = doc.read_text(encoding="utf-8").strip()
        assert len(content) > 50, f"Doc page {doc.name} appears incomplete or empty."
        assert content.startswith("# "), f"Doc page {doc.name} missing h1 heading."
