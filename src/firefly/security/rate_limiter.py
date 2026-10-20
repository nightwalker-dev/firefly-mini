"""Multi-bucket sliding-window rate limiters for destructive operations and input-control (Feature 98)."""

from __future__ import annotations

import collections
import re
import time
from typing import Deque, Dict, Optional, Tuple


class RateLimitExceeded(RuntimeError):
    """Raised when an operation exceeds safety rate limits."""

    def __init__(self, category: str, limit: int, window_seconds: float, current_count: int):
        super().__init__(
            f"Rate limit exceeded for '{category}': {current_count} calls within "
            f"{window_seconds:.1f}s window (limit is {limit})."
        )
        self.category = category
        self.limit = limit
        self.window_seconds = window_seconds
        self.current_count = current_count


class SecurityRateLimiter:
    """Sliding-window rate limiter specialized for defense against rapid destructive calls."""

    DESTRUCTIVE_PATTERN = re.compile(
        r"\b(?:rm|shred|truncate|dd|mkfs|fdisk|parted|wipefs|kill|killall|pkill|"
        r"DROP\s+DATABASE|DROP\s+TABLE|TRUNCATE\s+TABLE)\b",
        re.IGNORECASE,
    )

    def __init__(
        self,
        destructive_limit: int = 5,
        destructive_window_sec: float = 60.0,
        input_limit: int = 30,
        input_window_sec: float = 10.0,
        mfa_limit: int = 3,
        mfa_window_sec: float = 300.0,
    ) -> None:
        self.limits: Dict[str, Tuple[int, float]] = {
            "destructive": (destructive_limit, destructive_window_sec),
            "input_control": (input_limit, input_window_sec),
            "mfa_attempts": (mfa_limit, mfa_window_sec),
        }
        self._history: Dict[str, Deque[float]] = collections.defaultdict(collections.deque)

    def is_destructive_command(self, command: str) -> bool:
        """Determines if a command matches common destructive verbs."""
        return bool(self.DESTRUCTIVE_PATTERN.search(command))

    def check(self, category: str, cost: int = 1) -> Tuple[bool, str]:
        """Checks if recording `cost` events would violate the category rate limit.

        Returns (allowed: bool, reason: str).
        """
        now = time.monotonic()
        limit, window = self.limits.get(category, (100, 60.0))
        queue = self._history[category]

        # Evict timestamps older than the sliding window
        while queue and queue[0] < now - window:
            queue.popleft()

        if len(queue) + cost > limit:
            return (
                False,
                f"Rate limit for '{category}' reached ({len(queue)}/{limit} within {window:.0f}s).",
            )
        return True, "Within safe rate limits."

    def record(self, category: str, cost: int = 1) -> None:
        """Records `cost` events into the rate limit tracking queue."""
        now = time.monotonic()
        queue = self._history[category]
        for _ in range(cost):
            queue.append(now)

    def acquire(self, category: str, cost: int = 1) -> bool:
        """Combines check and record; raises RateLimitExceeded if limit breached."""
        allowed, reason = self.check(category, cost)
        if not allowed:
            limit, window = self.limits.get(category, (100, 60.0))
            raise RateLimitExceeded(
                category=category,
                limit=limit,
                window_seconds=window,
                current_count=len(self._history[category]),
            )
        self.record(category, cost)
        return True

    def reset(self, category: Optional[str] = None) -> None:
        """Clears history for a specific category or all categories."""
        if category:
            self._history[category].clear()
        else:
            self._history.clear()


# Global default rate limiter
default_rate_limiter = SecurityRateLimiter()
