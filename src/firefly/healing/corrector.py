"""ReAct self-correction engine: automated elevation, retry budgeting, and guardrail validation."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from firefly.core.guardrails import Action, Guardrails, Verdict
from firefly.core.logger import checkpointer
from firefly.healing.classifier import ErrorCategory, ErrorClassifier
from firefly.healing.heuristics import (
    did_you_mean,
    make_dry_run_command,
    resolve_fuzzy_path,
    suggest_package,
)
from firefly.healing.lessons import LessonsStore
from firefly.healing.watchdog import LoopDetector


@dataclass
class CorrectionProposal:
    """A proposed remedial action to heal a failed execution."""

    original_command: str
    proposed_command: str
    confidence: float
    explanation: str
    category: ErrorCategory
    requires_mfa: bool = False
    ask_user: bool = False
    dry_run_command: Optional[str] = None
    verdict: Optional[Verdict] = None

    @property
    def is_executable(self) -> bool:
        """Indicates whether this proposal is safe to execute."""
        if not self.verdict:
            return False
        return self.verdict.action != Action.BLOCK and self.confidence > 0.0


class SelfCorrector:
    """Generates safe, guardrail-verified remediation proposals for failed commands."""

    def __init__(
        self,
        guardrails: Optional[Guardrails] = None,
        lessons_store: Optional[LessonsStore] = None,
        loop_detector: Optional[LoopDetector] = None,
        confidence_threshold: float = 0.6,
        max_retries: int = 3,
    ) -> None:
        self.guardrails = guardrails or Guardrails()
        self.lessons_store = lessons_store or LessonsStore()
        self.loop_detector = loop_detector or LoopDetector(max_repeats=3)
        self.confidence_threshold = confidence_threshold
        self.max_retries = max_retries

    def calculate_backoff(
        self,
        attempt: int,
        base_delay: float = 0.2,
        max_delay: float = 5.0,
        with_jitter: bool = True,
    ) -> float:
        """Calculates exponential backoff delay with randomized jitter."""
        delay = min(base_delay * (2**attempt), max_delay)
        if with_jitter:
            delay += random.uniform(0, base_delay)
        return round(delay, 3)

    def rollback_if_failed(
        self, checkpoint_id: Optional[str], dest: Optional[Path | str] = None
    ) -> bool:
        """Rolls back the system to the pre-execution checkpoint if a fix degrades state."""
        if not checkpoint_id:
            return False
        target = Path(dest) if dest else Path.cwd()
        return checkpointer.restore_checkpoint(checkpoint_id, target)

    def propose_correction(
        self,
        command: str,
        raw_error: str,
        exit_code: int = 1,
        cwd: Optional[str] = None,
    ) -> Optional[CorrectionProposal]:
        """Analyzes command failure and produces a safe, guardrail-vetted remediation proposal."""
        action_sig = f"{command.strip()}::{exit_code}"

        # 1. Feature 27: Loop Detection
        if self.loop_detector.record_action(action_sig, failed=True):
            return CorrectionProposal(
                original_command=command,
                proposed_command="",
                confidence=0.0,
                explanation="Execution loop detected: action failed 3 times consecutively. Halting cycle.",
                category=ErrorCategory.LOGIC,
                ask_user=True,
                verdict=None,
            )

        # 2. Feature 35: Lessons Learned Memory Check
        past_lesson = self.lessons_store.find_lesson(raw_error, command)
        if past_lesson:
            verdict = self.guardrails.check_command(past_lesson.successful_fix, cwd=cwd)
            if verdict.action != Action.BLOCK:
                return CorrectionProposal(
                    original_command=command,
                    proposed_command=past_lesson.successful_fix,
                    confidence=0.95,
                    explanation=f"Applied proven fix from lessons learned (used {past_lesson.success_count}x).",
                    category=ErrorCategory.LOGIC,
                    requires_mfa=(verdict.action == Action.MFA),
                    ask_user=False,
                    verdict=verdict,
                )

        # 3. Feature 16: Error Classification
        err_detail = ErrorClassifier.classify(raw_error, exit_code=exit_code, command=command)

        proposed_cmd: Optional[str] = None
        confidence: float = 0.5
        explanation: str = err_detail.message
        requires_mfa: bool = False

        # 4. Feature 18: Auto-Elevation with MFA
        if err_detail.category == ErrorCategory.PERMISSION:
            clean_cmd = command.strip()
            if not clean_cmd.startswith("sudo"):
                proposed_cmd = f"sudo {clean_cmd}"
                confidence = 0.85
                explanation = "Operation denied: elevated permissions required. Proposing sudo execution via MFA gate."
                requires_mfa = True

        # 5. Feature 22 & 23: Typo Correction & Package Suggestions
        elif err_detail.category == ErrorCategory.MISSING_DEP:
            tokens = command.strip().split()
            binary = tokens[0] if tokens else ""

            # Try typo detection first
            typo_fix = did_you_mean(command)
            if typo_fix:
                proposed_cmd = typo_fix
                confidence = 0.80
                explanation = f"Command typo detected: did you mean '{typo_fix.split()[0]}'?"
            else:
                # Try package suggestion
                pkg_info = suggest_package(binary)
                if pkg_info:
                    pkg_name, install_cmd = pkg_info
                    proposed_cmd = install_cmd
                    confidence = 0.75
                    explanation = f"Missing utility '{binary}'. Proposing package installation for '{pkg_name}'."
                    requires_mfa = True

        # 6. Feature 24: Fuzzy Path Resolution
        elif (
            err_detail.category == ErrorCategory.LOGIC and "No such file or directory" in raw_error
        ):
            tokens = command.strip().split()
            # Attempt to resolve the last token or argument as a path
            for token in reversed(tokens[1:]):
                if not token.startswith("-"):
                    fuzzy_match = resolve_fuzzy_path(token, cwd=cwd)
                    if fuzzy_match:
                        proposed_cmd = command.replace(token, str(fuzzy_match))
                        confidence = 0.70
                        explanation = f"Path '{token}' not found. Resolved to nearest match '{fuzzy_match.name}'."
                        break

        if not proposed_cmd:
            return None

        # 7. Feature 20: Mandatory Guardrail Re-Validation
        verdict = self.guardrails.check_command(proposed_cmd, cwd=cwd)
        if verdict.action == Action.BLOCK:
            return CorrectionProposal(
                original_command=command,
                proposed_command=proposed_cmd,
                confidence=0.0,
                explanation=f"Remediation blocked by safety guardrails: {verdict.summary()}",
                category=err_detail.category,
                ask_user=True,
                verdict=verdict,
            )

        if verdict.action == Action.MFA:
            requires_mfa = True

        # 8. Feature 25: Dry-Run Generation for Risky Commands
        dry_run = make_dry_run_command(proposed_cmd)

        # 9. Feature 21: Confidence Score Evaluation
        ask_user = confidence < self.confidence_threshold

        return CorrectionProposal(
            original_command=command,
            proposed_command=proposed_cmd,
            confidence=confidence,
            explanation=explanation,
            category=err_detail.category,
            requires_mfa=requires_mfa,
            ask_user=ask_user,
            dry_run_command=dry_run,
            verdict=verdict,
        )
