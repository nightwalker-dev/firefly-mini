"""Fallback tool chains for environment and desktop automation dependencies."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from firefly.core.result import Err, Ok, Result


@dataclass
class FallbackCandidate:
    """A tool candidate in a fallback resolution chain."""

    name: str
    binary: str
    command_builder: Callable[[Dict[str, Any]], List[str]]
    is_available_check: Optional[Callable[[], bool]] = None


class ToolFallbackChain:
    """Executes actions across a prioritized sequence of system tool backends."""

    def __init__(self) -> None:
        self._chains: Dict[str, List[FallbackCandidate]] = {}
        self._setup_default_chains()

    def register_candidate(self, chain_name: str, candidate: FallbackCandidate) -> None:
        """Adds a candidate to a named fallback chain."""
        if chain_name not in self._chains:
            self._chains[chain_name] = []
        self._chains[chain_name].append(candidate)

    def get_available_candidate(self, chain_name: str) -> Optional[FallbackCandidate]:
        """Finds the first executable candidate in the chain."""
        candidates = self._chains.get(chain_name, [])
        for cand in candidates:
            if cand.is_available_check:
                if cand.is_available_check():
                    return cand
            elif shutil.which(cand.binary) is not None:
                return cand
        return None

    def execute(self, chain_name: str, params: Dict[str, Any]) -> Result[Dict[str, Any], str]:
        """Iterates through candidate backends until one successfully executes the action."""
        candidates = self._chains.get(chain_name, [])
        if not candidates:
            return Err(f"No fallback chain registered for '{chain_name}'")

        last_error = "No available candidates"
        for cand in candidates:
            available = False
            if cand.is_available_check:
                available = cand.is_available_check()
            else:
                available = shutil.which(cand.binary) is not None

            if not available:
                continue

            try:
                cmd = cand.command_builder(params)
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10.0)
                if proc.returncode == 0:
                    return Ok(
                        {
                            "tool_used": cand.name,
                            "binary": cand.binary,
                            "stdout": proc.stdout,
                            "stderr": proc.stderr,
                        }
                    )
                last_error = (
                    f"{cand.name} failed with exit code {proc.returncode}: {proc.stderr.strip()}"
                )
            except Exception as e:
                last_error = f"{cand.name} execution error: {e}"

        return Err(f"All fallback options exhausted for '{chain_name}'. Last error: {last_error}")

    def _setup_default_chains(self) -> None:
        # Keyboard typing chain: ydotool -> wtype -> xdotool
        self.register_candidate(
            "keyboard_type",
            FallbackCandidate(
                name="ydotool",
                binary="ydotool",
                command_builder=lambda p: ["ydotool", "type", str(p.get("text", ""))],
            ),
        )
        self.register_candidate(
            "keyboard_type",
            FallbackCandidate(
                name="wtype",
                binary="wtype",
                command_builder=lambda p: ["wtype", str(p.get("text", ""))],
            ),
        )
        self.register_candidate(
            "keyboard_type",
            FallbackCandidate(
                name="xdotool",
                binary="xdotool",
                command_builder=lambda p: ["xdotool", "type", str(p.get("text", ""))],
            ),
        )

        # Screenshot capture chain: grim -> scrot
        self.register_candidate(
            "screenshot",
            FallbackCandidate(
                name="grim",
                binary="grim",
                command_builder=lambda p: [
                    "grim",
                    str(p.get("output_path", "/tmp/firefly_screen.png")),
                ],
            ),
        )
        self.register_candidate(
            "screenshot",
            FallbackCandidate(
                name="scrot",
                binary="scrot",
                command_builder=lambda p: [
                    "scrot",
                    str(p.get("output_path", "/tmp/firefly_screen.png")),
                ],
            ),
        )


default_fallback_chain = ToolFallbackChain()
