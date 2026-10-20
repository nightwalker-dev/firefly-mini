"""Record and replay session execution streams for debugging and regression tests (Feature 114)."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from firefly.memory.redactor import SecretRedactor


@dataclass
class RecordedEvent:
    """An individual recorded interaction step in a session."""

    index: int
    timestamp: float
    kind: str  # "user_input", "thought", "tool_call", "tool_result", "agent_output"
    data: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SessionRecording:
    """Complete bundle of recorded interaction events for a session."""

    session_id: str
    created_at: float
    events: List[RecordedEvent] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "events": [e.to_dict() for e in self.events],
            "metadata": self.metadata,
        }


class SessionRecorder:
    """Captures ReAct turns, user inputs, and tool calls into deterministic recording bundles."""

    def __init__(self, session_id: Optional[str] = None) -> None:
        self.session_id = session_id or f"rec_{uuid.uuid4().hex[:10]}"
        self.recording = SessionRecording(
            session_id=self.session_id,
            created_at=time.time(),
        )

    def record(self, kind: str, data: Dict[str, Any]) -> RecordedEvent:
        """Appends a new interaction event to the recording, scrubbing any secrets."""
        clean_data: Dict[str, Any] = {}
        for k, v in data.items():
            if isinstance(v, str):
                clean_data[k] = SecretRedactor.redact(v)
            else:
                clean_data[k] = v

        event = RecordedEvent(
            index=len(self.recording.events),
            timestamp=time.time(),
            kind=kind,
            data=clean_data,
        )
        self.recording.events.append(event)
        return event

    def save(self, target_path: str | Path) -> Path:
        """Serializes the recording bundle to JSON."""
        p = Path(target_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.recording.to_dict(), indent=2), encoding="utf-8")
        return p

    @classmethod
    def load(cls, file_path: str | Path) -> SessionRecording:
        """Loads a recorded session bundle from disk."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Recording file not found: {p}")
        raw = json.loads(p.read_text(encoding="utf-8"))
        events = [RecordedEvent(**e) for e in raw.get("events", [])]
        return SessionRecording(
            session_id=raw["session_id"],
            created_at=raw["created_at"],
            events=events,
            metadata=raw.get("metadata", {}),
        )


class SessionPlayer:
    """Replays and compares live session events against a baseline recording to detect regressions."""

    def __init__(self, baseline: SessionRecording) -> None:
        self.baseline = baseline

    def verify_against(self, actual_events: List[RecordedEvent]) -> Tuple[bool, List[str]]:
        """Verifies if a new run reproduced the expected sequence of tool calls and actions.

        Returns (is_conforming: bool, discrepancies: List[str]).
        """
        discrepancies: List[str] = []

        # Filter to deterministic semantic events (tool calls and results)
        expected_semantic = [
            e for e in self.baseline.events if e.kind in ("tool_call", "agent_output")
        ]
        actual_semantic = [e for e in actual_events if e.kind in ("tool_call", "agent_output")]

        if len(actual_semantic) != len(expected_semantic):
            discrepancies.append(
                f"Event count mismatch: expected {len(expected_semantic)} "
                f"semantic actions, observed {len(actual_semantic)}."
            )

        for i, (exp, act) in enumerate(zip(expected_semantic, actual_semantic)):
            if exp.kind != act.kind:
                discrepancies.append(
                    f"Step {i}: kind mismatch (expected '{exp.kind}', got '{act.kind}')."
                )
            if exp.kind == "tool_call":
                exp_tool = exp.data.get("tool")
                act_tool = act.data.get("tool")
                if exp_tool != act_tool:
                    discrepancies.append(
                        f"Step {i}: tool mismatch (expected '{exp_tool}', got '{act_tool}')."
                    )

        return (len(discrepancies) == 0, discrepancies)
