"""Session lifetime tracking, inactivity detection, and auto-lock guard (Feature 104)."""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Optional, Tuple


class SessionLockedError(PermissionError):
    """Raised when an operation is attempted while the agent session is locked."""

    def __init__(self, reason: str):
        super().__init__(f"Agent Session is LOCKED: {reason}. Unlock required to proceed.")
        self.reason = reason


class SessionGuard:
    """Monitors session duration and user inactivity, locking the agent when thresholds expire."""

    def __init__(
        self,
        inactivity_timeout_sec: float = 900.0,  # 15 minutes
        max_duration_sec: float = 28800.0,  # 8 hours
        unlock_pin: Optional[str] = None,
    ) -> None:
        self.inactivity_timeout_sec = inactivity_timeout_sec
        self.max_duration_sec = max_duration_sec
        self._session_id = f"sess_{uuid.uuid4().hex[:10]}"
        self._start_time = time.time()
        self._last_activity = self._start_time
        self._is_locked = False
        self._lock_reason: Optional[str] = None
        self._pin_hash = (
            hashlib.sha256(unlock_pin.encode("utf-8")).hexdigest() if unlock_pin else None
        )

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def is_locked(self) -> bool:
        # Check on access whether timeout has lapsed
        self.check_session()
        return self._is_locked

    @property
    def lock_reason(self) -> Optional[str]:
        return self._lock_reason

    def record_activity(self) -> None:
        """Updates last activity timestamp; raises SessionLockedError if currently locked."""
        if self._is_locked:
            raise SessionLockedError(self._lock_reason or "Session locked.")
        self._last_activity = time.time()

    def check_session(self) -> Tuple[bool, str]:
        """Validates session health against inactivity and duration limits.

        Returns (valid: bool, status_msg: str).
        """
        now = time.time()

        if self._is_locked:
            return False, f"Session is locked ({self._lock_reason})."

        # Check inactivity timeout
        idle_duration = now - self._last_activity
        if idle_duration > self.inactivity_timeout_sec:
            self.lock(f"Inactivity timeout expired ({idle_duration:.0f}s idle).")
            return False, self._lock_reason or "Inactivity lock."

        # Check maximum overall session lifespan
        total_duration = now - self._start_time
        if total_duration > self.max_duration_sec:
            self.lock(f"Maximum session lifespan reached ({total_duration:.0f}s elapsed).")
            return False, self._lock_reason or "Lifespan lock."

        remaining_idle = self.inactivity_timeout_sec - idle_duration
        return True, f"Session active ({remaining_idle:.0f}s idle time remaining)."

    def lock(self, reason: str = "Manual lock requested") -> None:
        """Immediately locks the agent session."""
        self._is_locked = True
        self._lock_reason = reason

    def unlock(self, pin: Optional[str] = None) -> bool:
        """Unlocks the session if PIN matches or no PIN is configured."""
        if self._pin_hash:
            if not pin:
                return False
            given_hash = hashlib.sha256(pin.encode("utf-8")).hexdigest()
            if given_hash != self._pin_hash:
                return False

        self._is_locked = False
        self._lock_reason = None
        self._last_activity = time.time()
        return True

    def reset_session(self) -> None:
        """Starts a fresh session."""
        self._session_id = f"sess_{uuid.uuid4().hex[:10]}"
        self._start_time = time.time()
        self._last_activity = self._start_time
        self._is_locked = False
        self._lock_reason = None


# Global default session guard
default_session_guard = SessionGuard()
