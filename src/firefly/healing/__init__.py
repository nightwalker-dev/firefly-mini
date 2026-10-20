"""Self-healing and auto-error-correction subsystem for Firefly Mini."""

from __future__ import annotations

from firefly.healing.classifier import ErrorCategory, ErrorClassifier, ErrorDetail, FireflyErrorCode
from firefly.healing.corrector import CorrectionProposal, SelfCorrector
from firefly.healing.doctor import DoctorCheck, FireflyDoctor
from firefly.healing.fallbacks import FallbackCandidate, ToolFallbackChain, default_fallback_chain
from firefly.healing.heuristics import (
    did_you_mean,
    make_dry_run_command,
    resolve_fuzzy_path,
    suggest_package,
)
from firefly.healing.lessons import Lesson, LessonsStore
from firefly.healing.repair import ConfigAutoRepair, JSONRepair
from firefly.healing.verifier import (
    CommandExitZeroCondition,
    DirectoryExistsCondition,
    FileContainsCondition,
    FileExistsCondition,
    PortListeningCondition,
    Postcondition,
    ProcessRunningCondition,
    TaskVerifier,
)
from firefly.healing.watchdog import LoopDetector, SafeSubprocessWatchdog, WatchdogResult

__all__ = [
    "ErrorCategory",
    "FireflyErrorCode",
    "ErrorDetail",
    "ErrorClassifier",
    "CorrectionProposal",
    "SelfCorrector",
    "DoctorCheck",
    "FireflyDoctor",
    "FallbackCandidate",
    "ToolFallbackChain",
    "default_fallback_chain",
    "did_you_mean",
    "suggest_package",
    "resolve_fuzzy_path",
    "make_dry_run_command",
    "Lesson",
    "LessonsStore",
    "ConfigAutoRepair",
    "JSONRepair",
    "Postcondition",
    "FileExistsCondition",
    "FileContainsCondition",
    "DirectoryExistsCondition",
    "ProcessRunningCondition",
    "PortListeningCondition",
    "CommandExitZeroCondition",
    "TaskVerifier",
    "LoopDetector",
    "SafeSubprocessWatchdog",
    "WatchdogResult",
]
