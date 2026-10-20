"""Comprehensive test suite for Phase 2: Auto Error Correction & Self-Healing (Features 16-35)."""

import json

from firefly.agent.reflector import Reflector
from firefly.core.guardrails import Action, Guardrails, Risk
from firefly.healing.classifier import ErrorCategory, ErrorClassifier, FireflyErrorCode
from firefly.healing.corrector import SelfCorrector
from firefly.healing.doctor import FireflyDoctor
from firefly.healing.fallbacks import FallbackCandidate, ToolFallbackChain
from firefly.healing.heuristics import (
    did_you_mean,
    levenshtein_distance,
    make_dry_run_command,
    resolve_fuzzy_path,
    suggest_package,
)
from firefly.healing.lessons import LessonsStore
from firefly.healing.repair import ConfigAutoRepair, JSONRepair
from firefly.healing.verifier import (
    CommandExitZeroCondition,
    DirectoryExistsCondition,
    FileContainsCondition,
    FileExistsCondition,
    TaskVerifier,
)
from firefly.healing.watchdog import LoopDetector, SafeSubprocessWatchdog


# ==============================================================================
# Feature 16 & 34: Error Classifier & Structured Taxonomy
# ==============================================================================
def test_error_classifier_permission():
    detail = ErrorClassifier.classify("bash: /etc/shadow: Permission denied", exit_code=1)
    assert detail.category == ErrorCategory.PERMISSION
    assert detail.code == FireflyErrorCode.FF_1002_PERMISSION
    assert "https://docs.firefly.local/errors/ff-1002" in detail.docs_url


def test_error_classifier_missing_dep():
    detail = ErrorClassifier.classify(
        "dig: command not found", exit_code=127, command="dig example.com"
    )
    assert detail.category == ErrorCategory.MISSING_DEP
    assert detail.code == FireflyErrorCode.FF_1003_MISSING_DEP


def test_error_classifier_syntax():
    detail = ErrorClassifier.classify("bash: syntax error near unexpected token `fi'", exit_code=2)
    assert detail.category == ErrorCategory.SYNTAX
    assert detail.code == FireflyErrorCode.FF_1001_SYNTAX


def test_error_classifier_timeout():
    detail = ErrorClassifier.classify("Command timed out after 30 seconds", exit_code=124)
    assert detail.category == ErrorCategory.TIMEOUT
    assert detail.code == FireflyErrorCode.FF_1004_TIMEOUT


def test_error_classifier_resource():
    detail = ErrorClassifier.classify("cat: write error: No space left on device", exit_code=1)
    assert detail.category == ErrorCategory.RESOURCE
    assert detail.code == FireflyErrorCode.FF_1005_RESOURCE


def test_error_classifier_guardrail():
    detail = ErrorClassifier.classify(
        "Firefly Guardrail Block: Destructive command intercepted", exit_code=-1
    )
    assert detail.category == ErrorCategory.GUARDRAIL
    assert detail.code == FireflyErrorCode.FF_1007_GUARDRAIL_BLOCKED


# ==============================================================================
# Feature 17, 18, 19, 20, 21: Self-Correction Loop, Elevation, Guardrails, Scoring
# ==============================================================================
def test_self_corrector_auto_elevation():
    guardrails = Guardrails(auto_approve_max_risk=Risk.LOW)
    corrector = SelfCorrector(guardrails=guardrails)

    proposal = corrector.propose_correction(
        command="systemctl restart nginx",
        raw_error="Failed to restart nginx: Access denied / need to be root",
        exit_code=1,
    )
    assert proposal is not None
    assert proposal.proposed_command == "sudo systemctl restart nginx"
    assert proposal.category == ErrorCategory.PERMISSION
    assert proposal.requires_mfa is True
    assert proposal.confidence >= 0.8
    assert proposal.is_executable is True


def test_self_corrector_guardrail_unbypassable():
    # If the suggested remediation is blocked by guardrails (e.g. rm -rf /), it MUST be blocked!
    guardrails = Guardrails(auto_approve_max_risk=Risk.LOW)
    corrector = SelfCorrector(guardrails=guardrails)

    # Simulate an error on a blocked command
    proposal = corrector.propose_correction(
        command="rm -rf /",
        raw_error="Permission denied",
        exit_code=1,
    )
    assert proposal is not None
    # Guardrail check on `sudo rm -rf /` MUST result in BLOCK verdict and is_executable False
    assert proposal.verdict is not None
    assert proposal.verdict.action == Action.BLOCK
    assert proposal.confidence == 0.0
    assert proposal.is_executable is False


def test_self_corrector_exponential_backoff_and_jitter():
    corrector = SelfCorrector()
    d0 = corrector.calculate_backoff(attempt=0, base_delay=0.1, with_jitter=False)
    d1 = corrector.calculate_backoff(attempt=1, base_delay=0.1, with_jitter=False)
    d2 = corrector.calculate_backoff(attempt=2, base_delay=0.1, with_jitter=False)

    assert d0 == 0.1
    assert d1 == 0.2
    assert d2 == 0.4

    # With jitter, delay should be >= base and <= 2*base
    dj = corrector.calculate_backoff(attempt=1, base_delay=0.1, with_jitter=True)
    assert 0.2 <= dj <= 0.35


def test_reflector_react_step_evaluation():
    corrector = SelfCorrector()
    reflector = Reflector(corrector=corrector)

    # Succeeded step
    eval_ok = reflector.evaluate_step("bash", json.dumps({"exit_code": 0, "stdout": "hello"}))
    assert eval_ok.is_success is True
    assert eval_ok.should_stop is False

    # Failed step triggering proposal
    eval_fail = reflector.evaluate_step(
        "bash",
        json.dumps({"exit_code": 1, "stderr": "Permission denied"}),
        command="systemctl restart ssh",
    )
    assert eval_fail.is_success is False
    assert eval_fail.category == "permission"
    assert eval_fail.suggested_action == "sudo systemctl restart ssh"


# ==============================================================================
# Feature 22: "Did you mean" typo correction
# ==============================================================================
def test_did_you_mean_levenshtein():
    assert levenshtein_distance("sl", "ls") == 1
    assert levenshtein_distance("gti", "git") == 1

    assert did_you_mean("gti status") == "git status"
    assert did_you_mean("sl -la") == "ls -la"
    assert did_you_mean("dcoker ps") == "docker ps"
    assert did_you_mean("unknowncompletelyrandomxyz") is None


# ==============================================================================
# Feature 23: Command-not-found package suggestions
# ==============================================================================
def test_suggest_package():
    res_deb = suggest_package("dig", distro="debian")
    assert res_deb is not None
    pkg, cmd = res_deb
    assert pkg == "dnsutils"
    assert "apt install -y dnsutils" in cmd

    res_arch = suggest_package("feh", distro="arch")
    assert res_arch is not None
    pkg_arch, cmd_arch = res_arch
    assert pkg_arch == "feh"
    assert "pacman -S --noconfirm feh" in cmd_arch

    assert suggest_package("nonexistent_binary_xyz") is None


# ==============================================================================
# Feature 24: Fuzzy Path Resolution
# ==============================================================================
def test_resolve_fuzzy_path(tmp_path):
    target_file = tmp_path / "firefly_config.json"
    target_file.write_text("{}")

    # Typo: firefly_confg.json
    resolved = resolve_fuzzy_path(str(tmp_path / "firefly_confg.json"))
    assert resolved is not None
    assert resolved.name == "firefly_config.json"


# ==============================================================================
# Feature 25: Dry-run for risky retries
# ==============================================================================
def test_make_dry_run_command():
    assert make_dry_run_command("apt install nginx") == "apt install nginx -s"
    assert make_dry_run_command("rsync -av /src /dest") == "rsync --dry-run -av /src /dest"
    assert make_dry_run_command("git clean -fd") == "git clean -fd --dry-run"
    assert make_dry_run_command("ls -la") is None


# ==============================================================================
# Feature 26: Automatic checkpoint rollback
# ==============================================================================
def test_checkpoint_rollback(tmp_path):
    from firefly.core.logger import checkpointer

    test_file = tmp_path / "data.txt"
    test_file.write_text("original content")

    cp_id = checkpointer.create_checkpoint(test_file, label="test_cp")
    assert cp_id is not None

    # Corrupt or modify data
    test_file.write_text("corrupted content")
    assert test_file.read_text() == "corrupted content"

    # Rollback
    corrector = SelfCorrector()
    success = corrector.rollback_if_failed(cp_id, dest=test_file)
    assert success is True
    assert test_file.read_text() == "original content"


# ==============================================================================
# Feature 27: Loop Detector
# ==============================================================================
def test_loop_detector():
    detector = LoopDetector(max_repeats=3)

    assert detector.record_action("action_A", failed=True) is False
    assert detector.record_action("action_A", failed=True) is False
    # 3rd failure of same action triggers loop detection
    assert detector.record_action("action_A", failed=True) is True

    # Reset
    detector.reset()
    assert detector.record_action("action_A", failed=True) is False


# ==============================================================================
# Feature 28: Task Verifier (Postconditions)
# ==============================================================================
def test_task_verifier_postconditions(tmp_path):
    f = tmp_path / "created.log"
    f.write_text("status=ready\n")

    conds = [
        FileExistsCondition(f, min_size_bytes=5),
        FileContainsCondition(f, "status=ready"),
        DirectoryExistsCondition(tmp_path),
        CommandExitZeroCondition("echo test"),
    ]

    res = TaskVerifier.verify(conds)
    assert res.is_ok() is True

    # Failing condition
    failing_conds = [FileExistsCondition(tmp_path / "missing.txt")]
    res_fail = TaskVerifier.verify(failing_conds)
    assert res_fail.is_err() is True
    assert "does not exist" in res_fail.unwrap_err()[0]


# ==============================================================================
# Feature 29: Self-diagnosis 'firefly doctor'
# ==============================================================================
def test_firefly_doctor():
    doctor = FireflyDoctor()
    checks = doctor.run_all()
    assert len(checks) >= 5

    py_check = next(c for c in checks if c.name == "Python Version")
    assert py_check.status == "PASS"

    guard_check = next(c for c in checks if c.name == "Guardrails Status")
    assert guard_check.status == "PASS"

    table = doctor.render_table()
    assert table is not None
    assert "Firefly Mini" in str(table.title)


# ==============================================================================
# Feature 30: Config Auto-Repair
# ==============================================================================
def test_config_auto_repair(tmp_path):
    cfg_file = tmp_path / "firefly.json"

    # 1. Healthy write
    res1 = ConfigAutoRepair.repair_json_file(cfg_file, default_content={"theme": "obsidian"})
    assert res1.is_ok()
    assert res1.unwrap()["theme"] == "obsidian"

    # Backup should exist
    bak_file = tmp_path / "firefly.json.bak"
    assert bak_file.exists()

    # 2. Corrupt file content
    cfg_file.write_text("{broken json syntax ...")

    # Repair should restore from backup
    res2 = ConfigAutoRepair.repair_json_file(cfg_file, default_content={"theme": "default"})
    assert res2.is_ok()
    assert res2.unwrap()["theme"] == "obsidian"


# ==============================================================================
# Feature 31: Tool-Call JSON Repair
# ==============================================================================
def test_json_repair():
    # Single quotes and trailing comma
    malformed1 = "{'tool': 'bash', 'args': {'cmd': 'ls',},}"
    repaired1 = JSONRepair.repair_json(malformed1)
    assert repaired1["tool"] == "bash"
    assert repaired1["args"]["cmd"] == "ls"

    # Markdown fence and unquoted keys
    malformed2 = "```json\n{tool: 'status', active: True}\n```"
    repaired2 = JSONRepair.repair_json(malformed2)
    assert repaired2["tool"] == "status"
    assert repaired2["active"] is True

    # Missing closing brace
    malformed3 = '{"message": "completed"'
    res3 = JSONRepair.repair_json(malformed3)
    assert res3["message"] == "completed"


# ==============================================================================
# Feature 32: Fallback Tool Chain
# ==============================================================================
def test_tool_fallback_chain():
    chain = ToolFallbackChain()

    chain.register_candidate(
        "test_action",
        FallbackCandidate(
            name="primary_failing",
            binary="false",
            command_builder=lambda p: ["false"],
        ),
    )
    chain.register_candidate(
        "test_action",
        FallbackCandidate(
            name="secondary_succeeding",
            binary="echo",
            command_builder=lambda p: ["echo", "fallback_success"],
        ),
    )

    result = chain.execute("test_action", {})
    assert result.is_ok() is True
    data = result.unwrap()
    assert data["tool_used"] == "secondary_succeeding"
    assert "fallback_success" in data["stdout"]


# ==============================================================================
# Feature 33: Safe Subprocess Timeout Watchdog
# ==============================================================================
def test_safe_subprocess_watchdog():
    # Quick successful process
    res_ok = SafeSubprocessWatchdog.run_safe(["echo", "quick"], timeout_sec=2.0)
    assert res_ok.timed_out is False
    assert res_ok.exit_code == 0
    assert "quick" in res_ok.stdout

    # Hung process with short timeout
    res_timeout = SafeSubprocessWatchdog.run_safe("sleep 10", timeout_sec=0.2, grace_period_sec=0.1)
    assert res_timeout.timed_out is True
    assert res_timeout.exit_code == 124
    assert "timed out" in res_timeout.stderr


# ==============================================================================
# Feature 35: Lessons Learned Store
# ==============================================================================
def test_lessons_learned_store(tmp_path):
    store_file = tmp_path / "lessons.json"
    store = LessonsStore(store_path=store_file)

    # Record remediation lesson with secret token that must be redacted
    lesson = store.record_success(
        error_pattern="Permission denied to access /dev/net",
        original_command="ip link set token='secret12345' dev eth0 up",
        fix_command="sudo ip link set dev eth0 up",
    )
    assert lesson.success_count == 1
    # Check secret redaction
    assert "secret12345" not in lesson.original_command

    # Lookup lesson
    found = store.find_lesson(
        error_text="Permission denied to access /dev/net",
        command="ip link set dev eth0 up",
    )
    # Substring match finds it
    assert found is not None
    assert found.successful_fix == "sudo ip link set dev eth0 up"
    assert found.success_count == 1
