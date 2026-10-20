"""Sandboxed shell executor with Guardrails integration, audit logging, and sudo handoff."""

from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from firefly.core.config import settings
from firefly.core.guardrails import Action, Guardrails, Risk, Verdict
from firefly.core.logger import checkpointer, logger
from firefly.security.audit import default_audit_chain
from firefly.security.explainer import default_block_explainer
from firefly.security.provenance import default_provenance
from firefly.security.rate_limiter import default_rate_limiter
from firefly.security.safe_mode import default_safe_mode
from firefly.security.session import default_session_guard
from firefly.security.snapshot import default_snapshot_manager


@dataclass
class ExecutionResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    verdict: Verdict
    approved: bool
    checkpoint_id: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0


class BashExecutor:
    """Executes system commands through the safety guardrail layer."""

    def __init__(
        self,
        guardrails: Optional[Guardrails] = None,
        confirm_callback: Optional[Callable[[Verdict], bool]] = None,
        mfa_callback: Optional[Callable[[Verdict], bool]] = None,
        cwd: Optional[str] = None,
    ):
        self.guardrails = guardrails or Guardrails(
            auto_approve_max_risk=settings.auto_approve_max_risk,
            cwd=cwd or os.getcwd(),
        )
        self.confirm_callback = confirm_callback or (lambda v: False)
        self.mfa_callback = mfa_callback or (lambda v: False)
        self.cwd = cwd or os.getcwd()

    def run(
        self,
        command: str,
        timeout: Optional[float] = None,
        auto_checkpoint: bool = True,
        env_override: Optional[dict[str, str]] = None,
    ) -> ExecutionResult:
        timeout = timeout or settings.shell_timeout
        start_time = time.monotonic()
        prov = default_provenance.get_current()
        prov_dict = prov.to_dict() if prov else None

        # Feature 104: Session lock & lifetime check
        sess_ok, sess_msg = default_session_guard.check_session()
        if not sess_ok:
            empty_v = Verdict(command, "shell", Action.BLOCK, Risk.CRITICAL)
            default_audit_chain.record(
                action="bash",
                command=command,
                status="session_locked",
                provenance=prov_dict,
            )
            return ExecutionResult(
                command=command,
                exit_code=-3,
                stdout="",
                stderr=f"Session Locked: {sess_msg}",
                duration_ms=0.0,
                verdict=empty_v,
                approved=False,
            )

        # Feature 103: Safe Mode check
        sm_ok, sm_reason = default_safe_mode.evaluate_command(command)
        if not sm_ok:
            empty_v = Verdict(command, "shell", Action.BLOCK, Risk.HIGH)
            default_audit_chain.record(
                action="bash",
                command=command,
                status="safe_mode_blocked",
                provenance=prov_dict,
            )
            return ExecutionResult(
                command=command,
                exit_code=-4,
                stdout="",
                stderr=f"Safe Mode Block: {sm_reason}",
                duration_ms=0.0,
                verdict=empty_v,
                approved=False,
            )

        # Feature 98: Rate Limiting on Destructive commands
        if default_rate_limiter.is_destructive_command(command):
            rl_ok, rl_reason = default_rate_limiter.check("destructive")
            if not rl_ok:
                empty_v = Verdict(command, "shell", Action.BLOCK, Risk.HIGH)
                default_audit_chain.record(
                    action="bash",
                    command=command,
                    status="rate_limit_blocked",
                    provenance=prov_dict,
                )
                return ExecutionResult(
                    command=command,
                    exit_code=-5,
                    stdout="",
                    stderr=f"Rate Limit Block: {rl_reason}",
                    duration_ms=0.0,
                    verdict=empty_v,
                    approved=False,
                )

        # Step 1: Guardrail Inspection
        verdict = self.guardrails.check_command(command, cwd=self.cwd)

        # Step 2: Enforcement & Escalation
        approved = False
        user_response = None

        if verdict.action == Action.BLOCK:
            explanation = default_block_explainer.explain(verdict)
            default_audit_chain.record(
                action="bash",
                command=command,
                status="blocked",
                provenance=prov_dict,
            )
            logger.log(
                kind="bash",
                action=command,
                risk_level=verdict.risk.name,
                verdict_action=verdict.action.value,
                approved=False,
                output_summary="BLOCKED_BY_GUARDRAIL",
                duration_ms=0.0,
            )
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Firefly Guardrail Block: {verdict.summary()}\n\n{explanation.format_text()}",
                duration_ms=0.0,
                verdict=verdict,
                approved=False,
            )

        elif verdict.action == Action.MFA:
            approved = self.mfa_callback(verdict)
            user_response = "MFA_PASSED" if approved else "MFA_REJECTED"

        elif verdict.action == Action.CONFIRM:
            approved = self.confirm_callback(verdict)
            user_response = "CONFIRMED" if approved else "REJECTED"

        elif verdict.action == Action.ALLOW:
            approved = True
            user_response = "AUTO_APPROVED"

        if not approved:
            default_audit_chain.record(
                action="bash",
                command=command,
                status="rejected",
                provenance=prov_dict,
            )
            logger.log(
                kind="bash",
                action=command,
                risk_level=verdict.risk.name,
                verdict_action=verdict.action.value,
                approved=False,
                user_response=user_response,
                output_summary="REJECTED_BY_USER",
                duration_ms=0.0,
            )
            return ExecutionResult(
                command=command,
                exit_code=-2,
                stdout="",
                stderr=f"Execution denied by policy/user: {verdict.summary()}",
                duration_ms=0.0,
                verdict=verdict,
                approved=False,
            )

        # Record destructive rate limiter if passed
        if default_rate_limiter.is_destructive_command(command):
            default_rate_limiter.record("destructive")

        # Feature 100: Pre-operation snapshot for bulk operations
        if default_snapshot_manager.is_bulk_operation(command):
            try:
                default_snapshot_manager.create_snapshot(
                    [self.cwd], reason=f"pre_bulk: {command[:50]}"
                )
            except Exception:
                pass

        # Step 3: Checkpointing for state-modifying operations
        checkpoint_id = None
        if auto_checkpoint and verdict.risk >= Risk.MEDIUM:
            # Checkpoint working directory or target paths if identifiable
            checkpoint_id = checkpointer.create_checkpoint(self.cwd, label="bash_exec")

        # Step 4: Execution via subprocess
        env = os.environ.copy()
        if env_override:
            env.update(env_override)

        from firefly.core.platform import resolve_shell

        shell_spec = resolve_shell(settings.shell)
        cmd_args = shell_spec.build_argv(command)

        try:
            proc = subprocess.run(
                cmd_args,
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            raw_out = proc.stdout or ""
            raw_err = proc.stderr or ""

            if len(raw_out) > settings.max_output_chars:
                excess = len(raw_out) - settings.max_output_chars
                stdout = (
                    raw_out[: settings.max_output_chars]
                    + f"\n[... {excess} characters truncated ...]"
                )
            else:
                stdout = raw_out

            if len(raw_err) > settings.max_output_chars:
                excess = len(raw_err) - settings.max_output_chars
                stderr = (
                    raw_err[: settings.max_output_chars]
                    + f"\n[... {excess} characters truncated ...]"
                )
            else:
                stderr = raw_err

            exit_code = proc.returncode

            # Handle directory changes in single-command mode if requested
            if command.strip().startswith("cd "):
                parts = command.strip().split(maxsplit=1)
                if len(parts) > 1:
                    raw_target = os.path.expanduser(parts[1].strip().strip('"').strip("'"))
                    target_path = Path(raw_target)
                    if not target_path.is_absolute():
                        target_path = Path(self.cwd) / target_path
                    new_dir = target_path.resolve()
                    if new_dir.is_dir():
                        self.cwd = str(new_dir)

        except subprocess.TimeoutExpired as te:
            out_val = (
                te.stdout.decode("utf-8", errors="replace")
                if isinstance(te.stdout, bytes)
                else (te.stdout or "")
            )
            stdout = str(out_val)[: settings.max_output_chars]
            stderr = f"Command timed out after {timeout} seconds"
            exit_code = 124
        except Exception as e:
            stdout = ""
            stderr = f"Subprocess error: {str(e)}"
            exit_code = 1

        duration_ms = (time.monotonic() - start_time) * 1000.0

        # Step 5: Audit telemetry logging
        summary = f"exit={exit_code} out_len={len(stdout)} err_len={len(stderr)}"
        default_audit_chain.record(
            action="bash",
            command=command,
            status=f"executed(exit={exit_code})",
            provenance=prov_dict,
        )
        logger.log(
            kind="bash",
            action=command,
            risk_level=verdict.risk.name,
            verdict_action=verdict.action.value,
            approved=True,
            user_response=user_response,
            output_summary=summary,
            duration_ms=duration_ms,
        )

        # Update session activity
        try:
            default_session_guard.record_activity()
        except Exception:
            pass

        return ExecutionResult(
            command=command,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            verdict=verdict,
            approved=True,
            checkpoint_id=checkpoint_id,
        )
