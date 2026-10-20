"""Integration and system tests for Firefly Mini core agent and subsystems."""

import pytest
from core.agent import FireflyAgent
from core.guardrails import Action
from core.logger import AuditLogger, CheckpointManager
from input_control.mouse_keyboard import InputController
from input_control.vision_ground import VisionGrounder
from main import app
from system.bash_executor import BashExecutor
from system.themer import DesktopThemer
from typer.testing import CliRunner

runner = CliRunner()


def test_bash_executor_safe_command(tmp_path):
    executor = BashExecutor(cwd=str(tmp_path))
    res = executor.run("echo 'cyber-cat'")
    assert res.success
    assert "cyber-cat" in res.stdout
    assert res.verdict.action == Action.ALLOW


def test_bash_executor_blocked_command(tmp_path):
    executor = BashExecutor(cwd=str(tmp_path))
    res = executor.run("rm -rf /")
    assert not res.success
    assert not res.approved
    assert "Guardrail Block" in res.stderr


def test_checkpoint_manager_roundtrip(tmp_path):
    cm = CheckpointManager(storage_dir=tmp_path / "checkpoints")
    target_file = tmp_path / "target.txt"
    target_file.write_text("v1_original")

    cp_id = cm.create_checkpoint(target_file, label="test")
    assert cp_id is not None

    target_file.write_text("v2_modified")
    assert target_file.read_text() == "v2_modified"

    ok = cm.restore_checkpoint(cp_id, target_file)
    assert ok
    assert target_file.read_text() == "v1_original"


def test_themer_generates_wallpaper(tmp_path):
    themer = DesktopThemer(config_dir=tmp_path / "config")
    wp = themer.generate_cyber_cat_wallpaper(output_path=tmp_path / "wp.png", width=640, height=360)
    assert wp.exists()
    assert wp.stat().st_size > 1000

    kitty_conf = themer.export_kitty_theme(out_path=tmp_path / "kitty.conf")
    assert kitty_conf.exists()
    assert "Firefly Mini" in kitty_conf.read_text()


def test_audit_logger_encryption(tmp_path):
    logger = AuditLogger(db_path=tmp_path / "audit.db", key_path=tmp_path / "audit.key")
    logger.log(
        kind="bash",
        action="ls -la",
        risk_level="SAFE",
        verdict_action="allow",
        approved=True,
        output_summary="listed 5 files",
    )
    records = logger.get_recent(limit=5)
    assert len(records) == 1
    assert records[0].action == "ls -la"
    assert records[0].approved is True


def test_vision_grounder_screen_capture(tmp_path):
    vg = VisionGrounder()
    out = vg.capture_screen(output_path=tmp_path / "cap.png")
    assert out is not None
    assert out.exists()
    w, h = vg.get_screen_size()
    assert w > 0 and h > 0


def test_input_controller_mouse_actions():
    ctrl = InputController()
    assert ctrl.move_mouse(100, 100) is True
    assert ctrl.click("left") is True
    ok, _ = ctrl.type_text("hello", target_is_terminal=False)
    assert ok is True


@pytest.mark.asyncio
async def test_agent_dispatch_tool_safe(tmp_path):
    agent = FireflyAgent()
    agent.bash.cwd = str(tmp_path)
    res_json = await agent.dispatch_tool("bash_run", {"command": "pwd"})
    assert str(tmp_path) in res_json


def test_cli_commands():
    # Test status
    res = runner.invoke(app, ["status"])
    assert res.exit_code == 0
    assert "Subsystem Readiness" in res.stdout

    # Test audit
    res = runner.invoke(app, ["audit", "-n", "3"])
    assert res.exit_code == 0

    # Test stop & reset
    res = runner.invoke(app, ["stop"])
    assert res.exit_code == 0
    res = runner.invoke(app, ["reset"])
    assert res.exit_code == 0
