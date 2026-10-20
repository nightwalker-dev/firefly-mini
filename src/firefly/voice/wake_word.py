"""Fuzzy & Phonetic Wake-Word Detection Engine for Firefly Mini."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from firefly.healing.heuristics import levenshtein_distance


class WakeWordMatcher:
    """Detects wake-words with fuzzy distance tolerance for accents and audio compression."""

    DEFAULT_WAKE_WORDS = [
        "firefly",
        "hey firefly",
        "fire fly",
        "fire-fly",
        "hi firefly",
        "cyber cat",
    ]

    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        max_distance: int = 3,
    ):
        self.wake_words = [w.lower().strip() for w in (wake_words or self.DEFAULT_WAKE_WORDS)]
        self.max_distance = max_distance

    def match(self, transcript: str) -> Tuple[bool, str, float]:
        """Evaluates whether transcript starts with or contains any configured wake-word.

        Returns:
            (is_matched, remaining_command, confidence)
        """
        clean = transcript.strip().lower()
        if not clean:
            return False, "", 0.0

        words = re.findall(r"\w+", clean)
        if not words:
            return False, clean, 0.0

        # 1. Exact or prefix match first (confidence = 1.0)
        for target in self.wake_words:
            target_words = target.split()
            n = len(target_words)
            if len(words) >= n and words[:n] == target_words:
                remaining = " ".join(words[n:]).strip()
                return True, remaining, 1.0

        # 2. Check full phrase search
        for target in self.wake_words:
            pattern = rf"\b{re.escape(target)}\b"
            match = re.search(pattern, clean)
            if match:
                remaining = clean[match.end() :].strip(" ,.!?;:")
                return True, remaining, 0.95

        # 3. Fuzzy match over initial 1 or 2 word combinations
        target_singles = [w for w in self.wake_words if " " not in w]
        if words and target_singles:
            first_word = words[0]
            for target in target_singles:
                dist = levenshtein_distance(first_word, target)
                if dist <= self.max_distance:
                    remaining = " ".join(words[1:]).strip()
                    conf = max(0.5, 1.0 - (dist / max(1, len(target))))
                    return True, remaining, round(conf, 2)

        # 4. Fuzzy match two-word combinations (e.g. "hey flyerfly")
        if len(words) >= 2:
            two_words = f"{words[0]} {words[1]}"
            for target in self.wake_words:
                dist = levenshtein_distance(two_words, target)
                if dist <= self.max_distance:
                    remaining = " ".join(words[2:]).strip()
                    conf = max(0.5, 1.0 - (dist / max(1, len(target))))
                    return True, remaining, round(conf, 2)

        return False, clean, 0.0


wake_matcher = WakeWordMatcher()
