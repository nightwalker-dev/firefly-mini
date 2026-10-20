"""Memory decay formulas, importance scoring, and automatic store compaction."""

from __future__ import annotations

import math
import re
import time
from typing import List, Optional

from firefly.memory.store import MemoryItem, MemoryLayer, MemoryStore


class MemoryDecayManager:
    """Calculates temporal decay and handles capacity-bounded compaction."""

    @staticmethod
    def calculate_decay_score(
        item: MemoryItem,
        current_time: Optional[float] = None,
        halflife_days: float = 7.0,
    ) -> float:
        """Computes current relevance score taking exponential decay and access boost into account."""
        if item.pinned:
            return item.importance

        now = current_time or time.time()
        elapsed_seconds = max(0.0, now - item.last_accessed_at)
        elapsed_days = elapsed_seconds / 86400.0

        # Exponential decay factor: N(t) = N0 * (1/2)^(t / halflife)
        decay_factor = 0.5 ** (elapsed_days / max(0.1, halflife_days))

        # Access count logarithmic reinforcement
        access_boost = min(2.0, 1.0 + 0.15 * math.log(max(1, item.access_count)))

        effective_score = item.importance * decay_factor * access_boost
        return max(0.0, min(1.0, round(effective_score, 4)))

    @staticmethod
    def score_importance(
        content: str,
        key: str = "",
        is_user_explicit: bool = False,
    ) -> float:
        """Determines importance weight (0.0 - 1.0) based on content semantics and source."""
        if is_user_explicit:
            return 0.95

        text = f"{key} {content}".lower()

        # High priority keywords: identity, directives, persistent policies
        high_patterns = [
            r"\b(prefer|always|never|require|my name is|call me|favorite|habit|rule)\b",
            r"\b(password|secret|auth|master|owner|identity)\b",
        ]
        for pat in high_patterns:
            if re.search(pat, text):
                return 0.9

        # Medium priority: project settings, tools, aliases
        medium_patterns = [
            r"\b(editor|theme|shell|command|alias|port|branch|repo|project|build)\b",
            r"\b(config|setting|workflow|routine)\b",
        ]
        for pat in medium_patterns:
            if re.search(pat, text):
                return 0.7

        # Default moderate score
        return 0.4

    @classmethod
    def compact(
        cls,
        store: MemoryStore,
        layer: Optional[MemoryLayer] = None,
        max_items: int = 500,
        prune_score_threshold: float = 0.08,
    ) -> int:
        """Evicts decayed, low-importance unpinned memories when capacity limits are reached."""
        items: List[MemoryItem] = store.list_memories(
            layer=layer, include_superseded=True, limit=5000
        )
        if len(items) <= max_items:
            return 0

        # Calculate decay scores for unpinned items
        unpinned = [it for it in items if not it.pinned]
        now = time.time()

        scored = [(it, cls.calculate_decay_score(it, current_time=now)) for it in unpinned]

        # Identify items below threshold or exceeding max_items
        scored.sort(key=lambda x: x[1])  # lowest scores first

        prune_targets: List[str] = []
        # 1. Prune all items below threshold
        for it, score in scored:
            if score <= prune_score_threshold:
                prune_targets.append(it.id)

        # 2. If still over capacity, prune lowest remaining until within limit
        remaining_count = len(items) - len(prune_targets)
        if remaining_count > max_items:
            excess = remaining_count - max_items
            for it, _ in scored:
                if it.id not in prune_targets:
                    prune_targets.append(it.id)
                    excess -= 1
                    if excess <= 0:
                        break

        # Delete pruned items from store
        deleted_count = 0
        for m_id in prune_targets:
            if store.delete_memory(m_id):
                deleted_count += 1

        return deleted_count
