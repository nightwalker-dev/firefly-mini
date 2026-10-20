"""Context-aware memory retrieval and contradiction handling."""

from __future__ import annotations

import time
from typing import List, Optional

from firefly.memory.decay import MemoryDecayManager
from firefly.memory.store import MemoryItem, MemoryLayer, MemoryStore


class ContradictionHandler:
    """Ensures newer facts supersede older conflicting facts while preserving historical trail."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def update_fact_with_supersession(
        self,
        key: str,
        new_content: str,
        importance: float = 0.85,
        pinned: bool = False,
        layer: MemoryLayer = MemoryLayer.SEMANTIC,
    ) -> MemoryItem:
        """Archives prior contradicting fact under superseded_by link, activating the new fact."""
        # 1. Add new memory item
        new_item = self.store.add_memory(
            layer=layer,
            key=key,
            content=new_content,
            importance=importance,
            pinned=pinned,
        )

        # 2. Find any active older memory with the same key and link it
        import sqlite3

        with sqlite3.connect(self.store.db_path) as conn:
            conn.execute(
                "UPDATE memories SET superseded_by = ? WHERE key = ? AND id != ? AND superseded_by IS NULL",
                (new_item.id, key, new_item.id),
            )
            conn.commit()

        return new_item


class ContextAwareRetriever:
    """Retrieves top-k relevant memories combining search, project scope, and decay scoring."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def retrieve_relevant(
        self,
        query: str,
        project_name: Optional[str] = None,
        top_k: int = 5,
    ) -> List[MemoryItem]:
        """Finds top-k active memories most relevant to query and context."""
        candidates: List[MemoryItem] = []

        # 1. Search semantic memory matching query terms
        semantic_matches = self.store.search(query, layer=MemoryLayer.SEMANTIC, limit=top_k * 2)
        candidates.extend(semantic_matches)

        # 2. Add project-scoped memories if specified
        if project_name:
            proj_prefix = f"project:{project_name}:"
            all_mems = self.store.list_memories(layer=MemoryLayer.SEMANTIC, limit=200)
            for m in all_mems:
                if m.key.startswith(proj_prefix) and m.id not in [c.id for c in candidates]:
                    candidates.append(m)

        # 3. Always include core user preferences if present
        pref_mems = [
            m
            for m in self.store.list_memories(layer=MemoryLayer.SEMANTIC, limit=50)
            if m.key.startswith("pref:") and m.id not in [c.id for c in candidates]
        ]
        candidates.extend(pref_mems[:3])

        # 4. Rank candidates by decay-adjusted relevance score
        now = time.time()
        scored_candidates = [
            (it, MemoryDecayManager.calculate_decay_score(it, current_time=now))
            for it in candidates
            if it.superseded_by is None
        ]
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # 5. Return deduplicated top-k items
        seen_ids = set()
        results: List[MemoryItem] = []
        for it, _ in scored_candidates:
            if it.id not in seen_ids:
                seen_ids.add(it.id)
                results.append(it)
                if len(results) >= top_k:
                    break

        return results

    def format_prompt_block(
        self,
        query: str,
        project_name: Optional[str] = None,
        top_k: int = 4,
    ) -> str:
        """Formats retrieved memories into an injection block for the planner system prompt."""
        mems = self.retrieve_relevant(query, project_name=project_name, top_k=top_k)
        if not mems:
            return ""

        lines = ["### [FIREFLY ADAPTIVE MEMORY]"]
        for m in mems:
            clean_key = m.key.replace("pref:", "preference: ").replace("project:", "project: ")
            lines.append(f"- **{clean_key}**: {m.content}")
        return "\n".join(lines)
