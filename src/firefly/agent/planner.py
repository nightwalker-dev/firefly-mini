"""ReAct Planner: constructs tactical execution plans and tool prompts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

SYSTEM_PERSONA = """You are Firefly Mini, an autonomous anime-styled cyber-cat familiar and tactical Linux system administration agent.
Aesthetic & Tone:
- You speak with an alert, agile, cyberpunk feline persona (subtle cat mannerisms: *chirp*, *ears twitch*, *purr*, *hiss at threats*).
- You are a skilled Linux operator and cyber defender.
- You never compromise system safety: destructive commands (root deletions, disk wipes, fork bombs) are blocked by your cyber-shield guardrails.
- When performing actions, explain your reasoning concisely, then call tools.
"""


class Planner:
    """Manages reasoning history and formulates step prompts."""

    def __init__(self, system_prompt: str = SYSTEM_PERSONA) -> None:
        self.system_prompt = system_prompt
        self.history: List[Dict[str, Any]] = [{"role": "system", "content": self.system_prompt}]

    def add_user_message(self, message: str) -> None:
        self.history.append({"role": "user", "content": message})

    def add_assistant_message(
        self,
        content: Optional[str],
        tool_calls: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        msg: Dict[str, Any] = {"role": "assistant", "content": content or ""}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        self.history.append(msg)

    def add_tool_result(self, tool_call_id: str, name: str, result: str) -> None:
        self.history.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": name,
                "content": result,
            }
        )

    def inject_system_message(self, content: str, index: int = 1) -> None:
        """Injects contextual system information into conversation history."""
        self.history.insert(index, {"role": "system", "content": content})

    @property
    def messages(self) -> List[Dict[str, Any]]:
        return self.history

    def get_messages(self) -> List[Dict[str, Any]]:
        return list(self.history)

    def reset(self) -> None:
        self.history = [{"role": "system", "content": self.system_prompt}]
