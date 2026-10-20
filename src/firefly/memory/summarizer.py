"""Session dialogue summarizer to maintain a bounded LLM context window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from firefly.memory.store import MemoryLayer, MemoryStore


@dataclass
class SummaryBlock:
    """A condensed representation of historical dialogue turns."""

    summary_text: str
    summarized_turn_count: int
    created_at: float


class SessionSummarizer:
    """Condenses older conversation turns into high-density summaries."""

    def __init__(
        self,
        store: Optional[MemoryStore] = None,
        max_active_turns: int = 10,
    ) -> None:
        self.store = store
        self.max_active_turns = max_active_turns

    def needs_summary(self, messages: List[Dict[str, Any]]) -> bool:
        """Determines if the message list exceeds the context threshold."""
        return len(messages) > self.max_active_turns

    def condense_messages(
        self,
        messages: List[Dict[str, Any]],
        keep_recent: int = 4,
    ) -> List[Dict[str, Any]]:
        """Extracts older messages, generates a summary prompt, and preserves recent turns."""
        if len(messages) <= keep_recent:
            return messages

        older_messages = messages[:-keep_recent]
        recent_messages = messages[-keep_recent:]

        # Extract salient points from older turns
        points: List[str] = []
        for msg in older_messages:
            role = msg.get("role", "unknown")
            content = str(msg.get("content", "")).strip()
            if not content:
                continue

            if role == "user":
                points.append(f"User requested: '{content[:120]}'")
            elif role == "assistant":
                if "tool_calls" in msg:
                    points.append("Assistant invoked execution tools.")
                else:
                    points.append(f"Assistant concluded: '{content[:100]}'")

        summary_body = " | ".join(points) if points else "Previous tasks completed."
        condensed_summary = (
            f"[Context Summary of earlier {len(older_messages)} turns: {summary_body}]"
        )

        # Record summary in episodic memory if store is available
        if self.store:
            self.store.add_memory(
                layer=MemoryLayer.EPISODIC,
                key=f"session_summary:{len(older_messages)}_turns",
                content=condensed_summary,
                importance=0.6,
                metadata={"summarized_turn_count": len(older_messages)},
            )

        # Prepend summary as system context message before recent turns
        summary_msg = {"role": "system", "content": condensed_summary}
        return [summary_msg] + recent_messages
