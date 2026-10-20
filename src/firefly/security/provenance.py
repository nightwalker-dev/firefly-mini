"""Command provenance: links every executed action to the prompt/thought that caused it (Feature 96)."""

from __future__ import annotations

import contextvars
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from firefly.memory.redactor import SecretRedactor


@dataclass
class CommandProvenance:
    """Audit metadata tracing the exact origin and reasoning of an executed command."""

    provenance_id: str
    prompt_id: str
    user_prompt: str
    thought: str
    trigger: str  # "user_direct", "self_healing", "voice_command", "routine", "subagent"
    timestamp: float
    parent_action_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_current_provenance: contextvars.ContextVar[Optional[CommandProvenance]] = contextvars.ContextVar(
    "_current_provenance", default=None
)


class ProvenanceTracker:
    """Async-safe context tracker for action provenance."""

    def __init__(self) -> None:
        self._history: list[CommandProvenance] = []

    def get_current(self) -> Optional[CommandProvenance]:
        """Retrieves the active provenance context for the current task/coroutine."""
        return _current_provenance.get()

    def create(
        self,
        user_prompt: str,
        thought: str = "",
        trigger: str = "user_direct",
        parent_action_id: Optional[str] = None,
        prompt_id: Optional[str] = None,
    ) -> CommandProvenance:
        """Instantiates a new CommandProvenance record with redacted prompt text."""
        prov = CommandProvenance(
            provenance_id=f"prov_{uuid.uuid4().hex[:12]}",
            prompt_id=prompt_id or f"prm_{uuid.uuid4().hex[:8]}",
            user_prompt=SecretRedactor.redact(user_prompt),
            thought=SecretRedactor.redact(thought),
            trigger=trigger,
            timestamp=time.time(),
            parent_action_id=parent_action_id,
        )
        self._history.append(prov)
        return prov

    class _ContextManager:
        def __init__(self, prov: CommandProvenance, tracker: ProvenanceTracker):
            self.prov = prov
            self.tracker = tracker
            self.token: Optional[contextvars.Token[Optional[CommandProvenance]]] = None

        def __enter__(self) -> CommandProvenance:
            self.token = _current_provenance.set(self.prov)
            return self.prov

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            if self.token:
                _current_provenance.reset(self.token)

    def track(
        self,
        user_prompt: str,
        thought: str = "",
        trigger: str = "user_direct",
        parent_action_id: Optional[str] = None,
        prompt_id: Optional[str] = None,
    ) -> _ContextManager:
        """Context manager setting active provenance for downstream command runs."""
        prov = self.create(
            user_prompt=user_prompt,
            thought=thought,
            trigger=trigger,
            parent_action_id=parent_action_id,
            prompt_id=prompt_id,
        )
        return self._ContextManager(prov, self)


# Global provenance tracker
default_provenance = ProvenanceTracker()
