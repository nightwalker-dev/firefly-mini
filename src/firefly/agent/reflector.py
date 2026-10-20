"""Reflector: step evaluation, postcondition checks, and loop termination analysis."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from firefly.healing.classifier import ErrorClassifier
from firefly.healing.corrector import SelfCorrector


@dataclass
class StepEvaluation:
    is_success: bool
    should_stop: bool
    feedback: str
    suggested_action: Optional[str] = None
    category: Optional[str] = None
    confidence: float = 1.0


class Reflector:
    """Evaluates observations from tool execution to steer planning and self-correction."""

    def __init__(self, corrector: Optional[SelfCorrector] = None) -> None:
        self.corrector = corrector

    def evaluate_step(
        self,
        tool_name: str,
        raw_output: str,
        command: Optional[str] = None,
    ) -> StepEvaluation:
        """Analyzes tool output and decides whether execution succeeded or proposes self-healing."""
        try:
            parsed = json.loads(raw_output)
            if isinstance(parsed, dict):
                exit_code = parsed.get("exit_code", 0)
                err_text = str(parsed.get("stderr") or parsed.get("error") or "")

                if "error" in parsed or parsed.get("success") is False or exit_code != 0:
                    err_msg = err_text or parsed.get("error") or "Execution failed"
                    err_detail = ErrorClassifier.classify(
                        err_msg, exit_code=exit_code if exit_code != 0 else 1, command=command
                    )

                    suggested_cmd = None
                    conf = 0.5
                    if self.corrector and command:
                        proposal = self.corrector.propose_correction(
                            command=command,
                            raw_error=err_msg,
                            exit_code=exit_code if exit_code != 0 else 1,
                        )
                        if proposal and proposal.is_executable:
                            suggested_cmd = proposal.proposed_command
                            conf = proposal.confidence

                    return StepEvaluation(
                        is_success=False,
                        should_stop=False,
                        feedback=f"Tool {tool_name} failed [{err_detail.code.value}]: {err_msg}",
                        suggested_action=suggested_cmd,
                        category=err_detail.category.value,
                        confidence=conf,
                    )
        except Exception:
            pass

        return StepEvaluation(
            is_success=True,
            should_stop=False,
            feedback=f"Tool {tool_name} executed successfully.",
        )
