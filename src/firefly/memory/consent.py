"""Explicit consent gate for personal identifiable information (PII) before memory persistence."""

from __future__ import annotations

import re
from typing import Callable, List, Optional, Tuple


class ConsentManager:
    """Detects personal information and requires explicit user consent before storing."""

    PII_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
        # Email Addresses
        (
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
            "Email Address",
        ),
        # Phone Numbers
        (
            re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
            "Phone Number",
        ),
        # Social Security / National ID numbers
        (
            re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "Social Security / National ID Number",
        ),
        # Credit Card Numbers
        (
            re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
            "Payment Card Number",
        ),
        # Real Name / Address introduction patterns
        (
            re.compile(
                r"\b(?:my real name is|i live at|my home address is|my birthday is)\s+([^\n.]+)",
                re.IGNORECASE,
            ),
            "Personal Identity / Location",
        ),
    ]

    def __init__(self, consent_callback: Optional[Callable[[str, str], bool]] = None) -> None:
        self.consent_callback = consent_callback or self._default_console_consent

    def detect_personal_data(self, text: str) -> Optional[str]:
        """Returns description of PII type detected in the text, or None if clean."""
        for pattern, desc in self.PII_PATTERNS:
            if pattern.search(text):
                return desc
        return None

    def requires_consent(self, text: str) -> bool:
        """Determines if the text contains sensitive personal data requiring authorization."""
        return self.detect_personal_data(text) is not None

    def request_consent(
        self, content: str, custom_callback: Optional[Callable[[str, str], bool]] = None
    ) -> bool:
        """Prompts for user approval before persisting personal information."""
        pii_type = self.detect_personal_data(content)
        if not pii_type:
            return True  # No PII detected, consent granted automatically

        callback = custom_callback or self.consent_callback
        return callback(pii_type, content)

    @staticmethod
    def _default_console_consent(pii_type: str, content: str) -> bool:
        """Fallback console confirmation prompt."""
        snippet = content[:80] + ("..." if len(content) > 80 else "")
        print("\n" + "=" * 60)
        print("🔒 [FIREFLY PRIVACY GATE: PERSONAL DATA DETECTED]")
        print(f"Detected Category: {pii_type}")
        print(f"Content Snippet:   {snippet}")
        print("=" * 60)
        try:
            ans = (
                input("Do you grant permission to remember this in long-term memory? [y/N]: ")
                .strip()
                .lower()
            )
            return ans in ("y", "yes")
        except (KeyboardInterrupt, EOFError):
            return False
