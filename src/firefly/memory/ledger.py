"""Tool reliability and performance ledger to guide planning decisions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import List, Optional

from firefly.memory.store import MemoryLayer, MemoryStore


@dataclass
class ToolStats:
    """Historical reliability metrics for an agent tool backend."""

    tool_name: str
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: float = 0.0
    last_error: Optional[str] = None

    @property
    def total_runs(self) -> int:
        return self.success_count + self.failure_count

    @property
    def reliability(self) -> float:
        if self.total_runs == 0:
            return 1.0  # Optimistic initial trust
        return round(self.success_count / self.total_runs, 3)

    @property
    def avg_latency_ms(self) -> float:
        if self.total_runs == 0:
            return 0.0
        return round(self.total_latency_ms / self.total_runs, 2)


class ToolReliabilityLedger:
    """Maintains success/failure metrics across tools so planners prioritize reliable options."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def _get_key(self, tool_name: str) -> str:
        return f"ledger:tool:{tool_name}"

    def record_run(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float = 0.0,
        error: Optional[str] = None,
    ) -> ToolStats:
        """Records an execution outcome and updates tool reliability metrics."""
        key = self._get_key(tool_name)
        mem = self.store.get_by_key(key, layer=MemoryLayer.SEMANTIC)

        if mem and mem.metadata:
            stats = ToolStats(**mem.metadata)
        else:
            stats = ToolStats(tool_name=tool_name)

        if success:
            stats.success_count += 1
        else:
            stats.failure_count += 1
            if error:
                stats.last_error = error[:200]

        stats.total_latency_ms += latency_ms

        self.store.add_memory(
            layer=MemoryLayer.SEMANTIC,
            key=key,
            content=f"Reliability: {stats.reliability:.1%} ({stats.success_count}/{stats.total_runs})",
            importance=0.85,
            pinned=True,
            metadata=asdict(stats),
        )
        return stats

    def get_stats(self, tool_name: str) -> ToolStats:
        """Retrieves statistics for a specific tool."""
        key = self._get_key(tool_name)
        mem = self.store.get_by_key(key, layer=MemoryLayer.SEMANTIC)
        if mem and mem.metadata:
            try:
                return ToolStats(**mem.metadata)
            except Exception:
                pass
        return ToolStats(tool_name=tool_name)

    def rank_tools(self, tool_candidates: List[str]) -> List[str]:
        """Sorts candidates by reliability score descending and latency ascending."""
        scored = []
        for name in tool_candidates:
            st = self.get_stats(name)
            scored.append((name, st.reliability, -st.avg_latency_ms))

        # Sort by reliability descending, then fastest average latency
        scored.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return [item[0] for item in scored]
