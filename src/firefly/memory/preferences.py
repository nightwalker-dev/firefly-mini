"""User preference learning, command habits, persona continuity, and routine detection."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from firefly.memory.store import MemoryLayer, MemoryStore


@dataclass
class PersonaState:
    """The cyber-cat familiar's ongoing relationship and memory of its master."""

    master_name: str = "Master"
    cat_name: str = "Firefly Mini"
    affinity_score: float = 1.0  # Grows with positive interactions
    total_interactions: int = 0
    favorite_commands: List[str] = field(default_factory=list)


class UserPreferencesManager:
    """Learns and persists user defaults across editor, shell, theme, and verbosity."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def get_preference(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Reads a stored user preference."""
        mem = self.store.get_by_key(f"pref:{key}", layer=MemoryLayer.SEMANTIC)
        if mem:
            return mem.content
        return default

    def set_preference(self, key: str, value: str, pinned: bool = True) -> None:
        """Stores or updates a user preference with high importance."""
        self.store.add_memory(
            layer=MemoryLayer.SEMANTIC,
            key=f"pref:{key}",
            content=value,
            importance=0.9,
            pinned=pinned,
        )

    def extract_preferences_from_text(self, text: str) -> Dict[str, str]:
        """Extracts user preferences expressed in natural dialogue."""
        learned: Dict[str, str] = {}
        t = text.lower()

        # Editor
        if re.search(r"\b(prefer|use|like)\s+(vim|neovim|nvim|nano|code|emacs|gedit)\b", t):
            match = re.search(r"\b(vim|neovim|nvim|nano|code|emacs|gedit)\b", t)
            if match:
                ed = match.group(1)
                learned["editor"] = "nvim" if ed in ("neovim", "nvim") else ed
                self.set_preference("editor", learned["editor"])

        # Shell
        if re.search(r"\b(my\s+shell\s+is|use|prefer)\s+(zsh|bash|fish)\b", t):
            match = re.search(r"\b(zsh|bash|fish)\b", t)
            if match:
                sh = match.group(1)
                learned["shell"] = sh
                self.set_preference("shell", sh)

        # Theme
        if re.search(
            r"\b(prefer|set|like|switch\s+to)\s+(tokyo-night|catppuccin|synthwave|obsidian|matrix)\b",
            t,
        ):
            match = re.search(r"\b(tokyo-night|catppuccin|synthwave|obsidian|matrix)\b", t)
            if match:
                thm = match.group(1)
                learned["theme"] = thm
                self.set_preference("theme", thm)

        return learned


class HabitLearner:
    """Tracks command usage frequency to identify user habits and recommend aliases."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def record_command(self, command: str) -> None:
        """Increments command usage count in habit tracking memory."""
        cmd_clean = command.strip()
        if not cmd_clean:
            return

        key = f"habit:cmd:{cmd_clean}"
        mem = self.store.get_by_key(key, layer=MemoryLayer.SEMANTIC)
        if mem:
            try:
                count = int(mem.content) + 1
            except ValueError:
                count = mem.metadata.get("count", 1) + 1
            meta = dict(mem.metadata)
            meta["count"] = count
            self.store.update_memory(mem.id, new_content=str(count), metadata=meta)
        else:
            self.store.add_memory(
                layer=MemoryLayer.SEMANTIC,
                key=key,
                content="1",
                importance=0.6,
                metadata={"command": cmd_clean, "count": 1},
            )

    def get_frequent_commands(self, min_count: int = 3) -> List[Tuple[str, int]]:
        """Returns commands invoked at least `min_count` times."""
        results: List[Tuple[str, int]] = []
        mems = self.store.list_memories(layer=MemoryLayer.SEMANTIC, limit=500)
        for m in mems:
            if m.key.startswith("habit:cmd:"):
                cmd = m.metadata.get("command") or m.key.replace("habit:cmd:", "")
                try:
                    count = int(m.content)
                except ValueError:
                    count = m.metadata.get("count", 1)
                if count >= min_count:
                    results.append((cmd, count))
        results.sort(key=lambda x: x[1], reverse=True)
        return results


class PersonaContinuity:
    """Maintains personality familiarity and conversational bond."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def get_state(self) -> PersonaState:
        """Loads persona state from semantic memory."""
        mem = self.store.get_by_key("persona:state", layer=MemoryLayer.SEMANTIC)
        if not mem:
            return PersonaState()
        try:
            data = mem.metadata
            return PersonaState(
                master_name=data.get("master_name", "Master"),
                cat_name=data.get("cat_name", "Firefly Mini"),
                affinity_score=data.get("affinity_score", 1.0),
                total_interactions=data.get("total_interactions", 0),
                favorite_commands=data.get("favorite_commands", []),
            )
        except Exception:
            return PersonaState()

    def record_interaction(self, user_name: Optional[str] = None) -> None:
        """Records a successful turn and increments bond score."""
        state = self.get_state()
        state.total_interactions += 1
        state.affinity_score = min(5.0, state.affinity_score + 0.05)
        if user_name:
            state.master_name = user_name

        self.store.add_memory(
            layer=MemoryLayer.SEMANTIC,
            key="persona:state",
            content=f"Bond with {state.master_name}: {state.affinity_score:.2f}",
            importance=0.95,
            pinned=True,
            metadata={
                "master_name": state.master_name,
                "cat_name": state.cat_name,
                "affinity_score": state.affinity_score,
                "total_interactions": state.total_interactions,
                "favorite_commands": state.favorite_commands,
            },
        )

    def generate_greeting(self) -> str:
        """Produces a familiarity-aware anime cyberpunk greeting."""
        state = self.get_state()
        if state.affinity_score > 3.0:
            return f"*purrs loudly and leans against your screen* Welcome back, {state.master_name}! All cyber systems are green."
        elif state.affinity_score > 1.5:
            return f"*twitches holographic ears* Greetings, {state.master_name}. Ready for terminal commands!"
        return (
            "*chirps alertly* Firefly Mini cyber-cat terminal online. How can I assist you, Master?"
        )


class RoutineDetector:
    """Detects recurring temporal workflows (e.g. Friday maintenance, pre-commit tests)."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def log_routine_action(self, action_name: str) -> None:
        """Records an execution event tagged with day of week and hour."""
        now = time.localtime()
        day_of_week = now.tm_wday  # 0=Monday, 4=Friday, 6=Sunday
        hour = now.tm_hour

        key = f"routine:log:{action_name}:{day_of_week}"
        mem = self.store.get_by_key(key, layer=MemoryLayer.EPISODIC)
        if mem:
            try:
                count = int(mem.content) + 1
            except ValueError:
                count = mem.metadata.get("count", 1) + 1
            meta = dict(mem.metadata)
            meta["count"] = count
            self.store.update_memory(mem.id, new_content=str(count), metadata=meta)
        else:
            self.store.add_memory(
                layer=MemoryLayer.EPISODIC,
                key=key,
                content="1",
                importance=0.5,
                metadata={"action": action_name, "day": day_of_week, "hour": hour, "count": 1},
            )

    def check_routine_suggestion(self, action_name: str) -> Optional[str]:
        """Checks if the user customarily runs this action today."""
        now = time.localtime()
        day_of_week = now.tm_wday
        days = ["Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays"]

        key = f"routine:log:{action_name}:{day_of_week}"
        mem = self.store.get_by_key(key, layer=MemoryLayer.EPISODIC)
        if mem:
            try:
                count = int(mem.content)
            except ValueError:
                count = mem.metadata.get("count", 1)
            if count >= 3:
                return f"You usually run '{action_name}' on {days[day_of_week]}."
        return None
