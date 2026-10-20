"""Postcondition verification engine for confirming task completion and system state."""

from __future__ import annotations

import socket
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from firefly.core.result import Err, Ok, Result


class Postcondition(ABC):
    """Abstract base class for post-execution state verification."""

    @abstractmethod
    def check(self) -> Result[bool, str]:
        """Executes verification check. Returns Ok(True) or Err(failure_reason)."""
        pass


@dataclass
class FileExistsCondition(Postcondition):
    """Verifies that a specified file exists and satisfies minimum size requirements."""

    path: Path | str
    min_size_bytes: int = 0

    def check(self) -> Result[bool, str]:
        p = Path(self.path)
        if not p.exists():
            return Err(f"Postcondition failed: file '{p}' does not exist.")
        if not p.is_file():
            return Err(f"Postcondition failed: path '{p}' exists but is not a regular file.")
        if p.stat().st_size < self.min_size_bytes:
            return Err(
                f"Postcondition failed: file '{p}' size ({p.stat().st_size} bytes) < expected {self.min_size_bytes} bytes."
            )
        return Ok(True)


@dataclass
class FileContainsCondition(Postcondition):
    """Verifies that a file contains a specific text pattern."""

    path: Path | str
    pattern: str

    def check(self) -> Result[bool, str]:
        p = Path(self.path)
        if not p.exists() or not p.is_file():
            return Err(f"Postcondition failed: file '{p}' does not exist.")
        try:
            content = p.read_text(encoding="utf-8")
            if self.pattern in content:
                return Ok(True)
            return Err(
                f"Postcondition failed: file '{p}' does not contain required text '{self.pattern}'."
            )
        except Exception as e:
            return Err(f"Postcondition failed: error reading file '{p}': {e}")


@dataclass
class DirectoryExistsCondition(Postcondition):
    """Verifies that a directory exists."""

    path: Path | str

    def check(self) -> Result[bool, str]:
        p = Path(self.path)
        if not p.exists() or not p.is_dir():
            return Err(f"Postcondition failed: directory '{p}' does not exist.")
        return Ok(True)


@dataclass
class ProcessRunningCondition(Postcondition):
    """Verifies that a named process or service is actively executing."""

    process_name: str

    def check(self) -> Result[bool, str]:
        try:
            res = subprocess.run(
                ["pgrep", "-f", self.process_name],
                capture_output=True,
                text=True,
            )
            if res.returncode == 0 and res.stdout.strip():
                return Ok(True)
            return Err(
                f"Postcondition failed: process matching '{self.process_name}' is not running."
            )
        except Exception as e:
            return Err(f"Postcondition failed: unable to check process '{self.process_name}': {e}")


@dataclass
class PortListeningCondition(Postcondition):
    """Verifies that a TCP network port is actively open and listening on localhost."""

    port: int
    host: str = "127.0.0.1"
    timeout_sec: float = 1.0

    def check(self) -> Result[bool, str]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(self.timeout_sec)
            result = s.connect_ex((self.host, self.port))
            if result == 0:
                return Ok(True)
            return Err(f"Postcondition failed: port {self.host}:{self.port} is not listening.")


@dataclass
class CommandExitZeroCondition(Postcondition):
    """Verifies that an inspection command returns exit code 0."""

    command: str
    timeout_sec: float = 5.0

    def check(self) -> Result[bool, str]:
        try:
            res = subprocess.run(
                self.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout_sec,
            )
            if res.returncode == 0:
                return Ok(True)
            return Err(
                f"Postcondition failed: command '{self.command}' exited with code {res.returncode}: {res.stderr.strip()}"
            )
        except Exception as e:
            return Err(f"Postcondition failed: execution error testing '{self.command}': {e}")


class TaskVerifier:
    """Evaluates one or more postconditions to verify task success."""

    @staticmethod
    def verify(conditions: Sequence[Postcondition]) -> Result[bool, List[str]]:
        """Evaluates all conditions and returns Ok(True) or Err(list_of_failures)."""
        failures: List[str] = []
        for cond in conditions:
            result = cond.check()
            if result.is_err():
                failures.append(result.unwrap_err())

        if failures:
            return Err(failures)
        return Ok(True)
