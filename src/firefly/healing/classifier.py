"""Structured error taxonomy and classification engine for Firefly Mini."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ErrorCategory(str, Enum):
    """Broad categorization of system and runtime execution errors."""

    SYNTAX = "syntax"
    PERMISSION = "permission"
    MISSING_DEP = "missing_dependency"
    TIMEOUT = "timeout"
    RESOURCE = "resource"
    LOGIC = "logic"
    GUARDRAIL = "guardrail"
    UNKNOWN = "unknown"


class FireflyErrorCode(str, Enum):
    """Unique error codes with corresponding documentation references."""

    FF_1001_SYNTAX = "FF-1001"
    FF_1002_PERMISSION = "FF-1002"
    FF_1003_MISSING_DEP = "FF-1003"
    FF_1004_TIMEOUT = "FF-1004"
    FF_1005_RESOURCE = "FF-1005"
    FF_1006_LOOP_DETECTED = "FF-1006"
    FF_1007_GUARDRAIL_BLOCKED = "FF-1007"
    FF_1008_POSTCONDITION_FAILED = "FF-1008"
    FF_1009_MALFORMED_OUTPUT = "FF-1009"
    FF_1010_CONFIG_CORRUPTED = "FF-1010"
    FF_1011_TOOL_FAILED = "FF-1011"
    FF_1099_UNKNOWN = "FF-1099"

    @property
    def docs_url(self) -> str:
        """Returns documentation anchor for this error code."""
        return f"https://docs.firefly.local/errors/{self.value.lower()}"


@dataclass
class ErrorDetail:
    """Structured description of an observed error."""

    category: ErrorCategory
    code: FireflyErrorCode
    message: str
    raw_output: str
    docs_url: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.docs_url:
            self.docs_url = self.code.docs_url


class ErrorClassifier:
    """Classifies terminal, tool, and agent errors into actionable taxonomy categories."""

    PATTERNS: List[Tuple[re.Pattern[str], ErrorCategory, FireflyErrorCode, str]] = [
        # Guardrail blocks
        (
            re.compile(
                r"Guardrail Block|BLOCKED_BY_GUARDRAIL|Execution denied by policy", re.IGNORECASE
            ),
            ErrorCategory.GUARDRAIL,
            FireflyErrorCode.FF_1007_GUARDRAIL_BLOCKED,
            "Operation intercepted and halted by security guardrails.",
        ),
        # Permissions / Sudo
        (
            re.compile(
                r"Permission denied|Operation not permitted|need to be root|must be run as root|are you root\?|sudo:\s*a password is required",
                re.IGNORECASE,
            ),
            ErrorCategory.PERMISSION,
            FireflyErrorCode.FF_1002_PERMISSION,
            "Elevation required: process lacks sufficient filesystem or capability privileges.",
        ),
        # Missing dependencies & commands
        (
            re.compile(
                r"command not found|No such file or directory.*executable|not found in PATH|is not recognized as an internal or external command|ModuleNotFoundError|ImportError",
                re.IGNORECASE,
            ),
            ErrorCategory.MISSING_DEP,
            FireflyErrorCode.FF_1003_MISSING_DEP,
            "Missing required command binary, package, or python module.",
        ),
        # Syntax / Parse errors
        (
            re.compile(
                r"syntax error|unexpected token|parse error|unrecognized option|invalid option|SyntaxError",
                re.IGNORECASE,
            ),
            ErrorCategory.SYNTAX,
            FireflyErrorCode.FF_1001_SYNTAX,
            "Command line, script, or payload syntax is malformed.",
        ),
        # Timeouts
        (
            re.compile(r"timed out|TimeoutExpired|Command.*exceeded timeout", re.IGNORECASE),
            ErrorCategory.TIMEOUT,
            FireflyErrorCode.FF_1004_TIMEOUT,
            "Execution exceeded time limit threshold.",
        ),
        # Resource exhaustion
        (
            re.compile(
                r"No space left on device|Out of memory|Cannot allocate memory|disk quota exceeded|Too many open files",
                re.IGNORECASE,
            ),
            ErrorCategory.RESOURCE,
            FireflyErrorCode.FF_1005_RESOURCE,
            "System resource constraint exhausted (disk, memory, or file descriptors).",
        ),
        # Missing files / paths
        (
            re.compile(r"No such file or directory|cannot access.*No such file", re.IGNORECASE),
            ErrorCategory.LOGIC,
            FireflyErrorCode.FF_1008_POSTCONDITION_FAILED,
            "Target file or directory path does not exist.",
        ),
    ]

    @classmethod
    def classify(
        cls,
        raw_output: str,
        exit_code: int = 1,
        command: Optional[str] = None,
    ) -> ErrorDetail:
        """Inspects exit code and error output text to assign a structured category."""
        text = raw_output.strip()

        # 1. Exit code specific fast paths
        if exit_code == 127:
            match = re.search(
                r"(\S+):\s*(?:command\s+not\s+found|not\s+found)", text, re.IGNORECASE
            )
            binary = match.group(1) if match else (command.split()[0] if command else "")
            return ErrorDetail(
                category=ErrorCategory.MISSING_DEP,
                code=FireflyErrorCode.FF_1003_MISSING_DEP,
                message=f"Command binary not found in PATH: {binary}".strip(),
                raw_output=text,
                details={"binary": binary, "exit_code": 127},
            )

        if exit_code == 126:
            return ErrorDetail(
                category=ErrorCategory.PERMISSION,
                code=FireflyErrorCode.FF_1002_PERMISSION,
                message="Command invoked cannot execute due to permission or format restrictions.",
                raw_output=text,
                details={"exit_code": 126},
            )

        if exit_code == 124:
            return ErrorDetail(
                category=ErrorCategory.TIMEOUT,
                code=FireflyErrorCode.FF_1004_TIMEOUT,
                message="Command was terminated because it exceeded the configured execution timeout.",
                raw_output=text,
                details={"exit_code": 124},
            )

        # 2. Pattern matching against error content
        for pattern, cat, code, explanation in cls.PATTERNS:
            if pattern.search(text):
                return ErrorDetail(
                    category=cat,
                    code=code,
                    message=explanation,
                    raw_output=text,
                    details={"exit_code": exit_code, "command": command},
                )

        # 3. Default fallback
        return ErrorDetail(
            category=ErrorCategory.UNKNOWN,
            code=FireflyErrorCode.FF_1099_UNKNOWN,
            message="Unrecognized failure condition.",
            raw_output=text,
            details={"exit_code": exit_code, "command": command},
        )
