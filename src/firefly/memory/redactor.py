"""Secret and credential redaction pipeline for memory and telemetry persistence."""

from __future__ import annotations

import re
from typing import List, Tuple


class SecretRedactor:
    """Detects and redacts credentials, passwords, private keys, and tokens."""

    REDACTION_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
        # SSH / RSA / EC Private Keys
        (
            re.compile(
                r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z]+ )?PRIVATE KEY-----",
                re.MULTILINE,
            ),
            "[REDACTED_PRIVATE_KEY]",
        ),
        # TOTP seeds / base32 secrets
        (
            re.compile(
                r"(\b(?:totp_secret|totp|seed)[\s=:]+)(?!\[REDACTED)['\"]?([A-Z2-7]{16,32})['\"]?",
                re.IGNORECASE,
            ),
            r"totp_secret=[REDACTED_TOTP_SEED]",
        ),
        # GitHub, Slack, AWS, HuggingFace, OpenAI API Tokens
        (
            re.compile(
                r"\b(?:ghp_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{82}|xox[baprs]-[a-zA-Z0-9-]{10,48}|sk-[a-zA-Z0-9_\-]{20,80}|hf_[a-zA-Z0-9]{34,40}|AKIA[0-9A-Z]{16})\b"
            ),
            "[REDACTED_API_TOKEN]",
        ),
        # Command line passwords & credentials
        (
            re.compile(
                r"(\b(?:--password|-p|password|passwd|secret|api_key|token)[\s=:]+)(?!\[REDACTED)['\"]?([^\s'\";]+)['\"]?",
                re.IGNORECASE,
            ),
            r"\1[REDACTED_SECRET]",
        ),
        # Sudo echo piping
        (
            re.compile(r"echo\s+['\"][^'\"]+['\"]\s*\|\s*sudo\s+-S", re.IGNORECASE),
            "echo [REDACTED_SUDO_INPUT] | sudo -S",
        ),
        # Database connection strings with credentials
        (
            re.compile(
                r"(?:postgres|mysql|mongodb|redis)://[^:]+:([^@]+)@",
                re.IGNORECASE,
            ),
            "[REDACTED_DB_CREDENTIALS]@",
        ),
        # Authorization Headers
        (
            re.compile(r"Authorization:\s*(?:Bearer|Basic)\s+[a-zA-Z0-9._~+/-]+=*", re.IGNORECASE),
            "Authorization: Bearer [REDACTED_AUTH_HEADER]",
        ),
    ]

    @classmethod
    def redact(cls, text: str) -> str:
        """Sanitizes sensitive information from input text string."""
        if not text:
            return ""
        result = text
        for pattern, replacement in cls.REDACTION_PATTERNS:
            result = pattern.sub(replacement, result)
        return result

    @classmethod
    def has_secrets(cls, text: str) -> bool:
        """Checks if the input text contains detectable secrets or credentials."""
        if not text:
            return False
        return any(pattern.search(text) is not None for pattern, _ in cls.REDACTION_PATTERNS)
