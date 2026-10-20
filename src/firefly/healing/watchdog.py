"""Loop detection and safe subprocess timeout watchdog with graceful termination."""

from __future__ import annotations

import collections
import subprocess
import time
from dataclasses import dataclass
from typing import Dict, List, Optional


class LoopDetector:
    """Detects recurring failing actions to prevent infinite agent retry loops."""

    def __init__(self, max_repeats: int = 3) -> None:
        self.max_repeats = max_repeats
        self._history: collections.deque[str] = collections.deque(maxlen=20)
        self._counts: Dict[str, int] = collections.defaultdict(int)

    def record_action(self, action_signature: str, failed: bool = True) -> bool:
        """Records an action execution. Returns True if an infinite loop is detected."""
        if not failed:
            # Succeeded actions break the failure cycle
            self._counts[action_signature] = 0
            return False

        self._history.append(action_signature)
        self._counts[action_signature] += 1

        # Check if the last max_repeats actions are identical
        if len(self._history) >= self.max_repeats:
            recent = list(self._history)[-self.max_repeats :]
            if all(sig == action_signature for sig in recent):
                return True

        return self._counts[action_signature] >= self.max_repeats

    def reset(self) -> None:
        """Clears action execution history."""
        self._history.clear()
        self._counts.clear()


@dataclass
class WatchdogResult:
    """Outcome of a monitored subprocess execution."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_sec: float


class SafeSubprocessWatchdog:
    """Executes subprocesses under a strict timeout with two-phase SIGTERM -> SIGKILL escalation."""

    @staticmethod
    def run_safe(
        cmd: List[str] | str,
        timeout_sec: float = 30.0,
        grace_period_sec: float = 0.5,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> WatchdogResult:
        """Runs a process safely, escalating from SIGTERM to SIGKILL on timeout to prevent hanging."""
        start_time = time.monotonic()
        use_shell = isinstance(cmd, str)

        from firefly.core.platform import kill_process_tree, new_process_group_kwargs

        try:
            # Process group isolation: start_new_session on POSIX, CREATE_NEW_PROCESS_GROUP on Windows
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=use_shell,
                cwd=cwd,
                env=env,
                **new_process_group_kwargs(),
            )
        except Exception as e:
            return WatchdogResult(
                exit_code=-1,
                stdout="",
                stderr=f"Process launch error: {e}",
                timed_out=False,
                duration_sec=time.monotonic() - start_time,
            )

        try:
            stdout_data, stderr_data = proc.communicate(timeout=timeout_sec)
            elapsed = time.monotonic() - start_time
            return WatchdogResult(
                exit_code=proc.returncode,
                stdout=stdout_data or "",
                stderr=stderr_data or "",
                timed_out=False,
                duration_sec=elapsed,
            )
        except subprocess.TimeoutExpired:
            # Cross-platform two-phase tree termination (SIGTERM -> SIGKILL on POSIX, TerminateProcess on Win)
            kill_process_tree(proc.pid, grace_sec=grace_period_sec)
            try:
                stdout_data, stderr_data = proc.communicate(timeout=0.2)
            except Exception:
                stdout_data, stderr_data = "", ""

            elapsed = time.monotonic() - start_time
            return WatchdogResult(
                exit_code=124,  # Standard timeout exit code
                stdout=stdout_data or "",
                stderr=(stderr_data or "")
                + f"\n[Watchdog: Execution timed out after {timeout_sec}s]",
                timed_out=True,
                duration_sec=elapsed,
            )
