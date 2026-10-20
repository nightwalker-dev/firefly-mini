"""System metrics collector: task success rate, retries, latency, tool reliability (Feature 107)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from firefly.core.config import settings


@dataclass
class ToolStats:
    """Invocation and reliability statistics for an individual tool."""

    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.calls == 0:
            return 100.0
        return (self.successes / self.calls) * 100.0

    @property
    def avg_duration_ms(self) -> float:
        if self.calls == 0:
            return 0.0
        return self.total_duration_ms / self.calls


@dataclass
class MetricsSummary:
    """Aggregated operational telemetry snapshot."""

    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    success_rate: float
    total_retries: int
    avg_latency_ms: float
    p95_latency_ms: float
    tool_reliability: Dict[str, Dict[str, Any]]
    guardrail_actions: Dict[str, int]


class MetricsCollector:
    """Collects and aggregates performance, reliability, and security telemetry."""

    def __init__(self, metrics_file: Optional[Path] = None) -> None:
        self.metrics_file = metrics_file or (settings.paths.data_dir / "metrics.json")
        self._latencies_ms: List[float] = []
        self._total_tasks = 0
        self._successful_tasks = 0
        self._failed_tasks = 0
        self._total_retries = 0
        self._tool_stats: Dict[str, ToolStats] = {}
        self._guardrail_counts: Dict[str, int] = {
            "allow": 0,
            "confirm": 0,
            "mfa": 0,
            "block": 0,
        }
        self.load()

    def record_task(
        self,
        success: bool,
        duration_ms: float,
        retries: int = 0,
    ) -> None:
        """Records the outcome of a user query or multi-step agent task."""
        self._total_tasks += 1
        if success:
            self._successful_tasks += 1
        else:
            self._failed_tasks += 1

        self._total_retries += retries
        self._latencies_ms.append(duration_ms)
        self.save()

    def record_tool_call(self, tool: str, success: bool, duration_ms: float) -> None:
        """Records an individual tool invocation and its latency."""
        if tool not in self._tool_stats:
            self._tool_stats[tool] = ToolStats()

        stat = self._tool_stats[tool]
        stat.calls += 1
        if success:
            stat.successes += 1
        else:
            stat.failures += 1
        stat.total_duration_ms += duration_ms
        self.save()

    def record_guardrail_action(self, action: str) -> None:
        """Tracks guardrail verdicts (allow, confirm, mfa, block)."""
        act = action.lower()
        if act in self._guardrail_counts:
            self._guardrail_counts[act] += 1
        else:
            self._guardrail_counts[act] = 1
        self.save()

    def get_summary(self) -> MetricsSummary:
        """Computes comprehensive metrics summary."""
        sr = (
            (self._successful_tasks / self._total_tasks * 100.0) if self._total_tasks > 0 else 100.0
        )
        avg_lat = sum(self._latencies_ms) / len(self._latencies_ms) if self._latencies_ms else 0.0

        p95 = 0.0
        if self._latencies_ms:
            sorted_lat = sorted(self._latencies_ms)
            idx = int(0.95 * len(sorted_lat))
            p95 = sorted_lat[min(idx, len(sorted_lat) - 1)]

        tool_report: Dict[str, Dict[str, Any]] = {}
        for t_name, stat in sorted(
            self._tool_stats.items(), key=lambda kv: kv[1].calls, reverse=True
        ):
            tool_report[t_name] = {
                "calls": stat.calls,
                "successes": stat.successes,
                "failures": stat.failures,
                "success_rate": round(stat.success_rate, 1),
                "avg_duration_ms": round(stat.avg_duration_ms, 2),
            }

        return MetricsSummary(
            total_tasks=self._total_tasks,
            successful_tasks=self._successful_tasks,
            failed_tasks=self._failed_tasks,
            success_rate=round(sr, 1),
            total_retries=self._total_retries,
            avg_latency_ms=round(avg_lat, 2),
            p95_latency_ms=round(p95, 2),
            tool_reliability=tool_report,
            guardrail_actions=dict(self._guardrail_counts),
        )

    def save(self) -> None:
        """Persists metrics state to disk."""
        try:
            self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "total_tasks": self._total_tasks,
                "successful_tasks": self._successful_tasks,
                "failed_tasks": self._failed_tasks,
                "total_retries": self._total_retries,
                "latencies_ms": self._latencies_ms[-1000:],  # keep last 1000
                "tool_stats": {k: asdict(v) for k, v in self._tool_stats.items()},
                "guardrail_counts": self._guardrail_counts,
            }
            self.metrics_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load(self) -> None:
        """Loads metrics from disk if present."""
        if not self.metrics_file.exists():
            return
        try:
            data = json.loads(self.metrics_file.read_text(encoding="utf-8"))
            self._total_tasks = data.get("total_tasks", 0)
            self._successful_tasks = data.get("successful_tasks", 0)
            self._failed_tasks = data.get("failed_tasks", 0)
            self._total_retries = data.get("total_retries", 0)
            self._latencies_ms = data.get("latencies_ms", [])
            self._tool_stats = {k: ToolStats(**v) for k, v in data.get("tool_stats", {}).items()}
            self._guardrail_counts = data.get(
                "guardrail_counts", {"allow": 0, "confirm": 0, "mfa": 0, "block": 0}
            )
        except Exception:
            pass

    def reset(self) -> None:
        """Clears all tracked metrics."""
        self._total_tasks = 0
        self._successful_tasks = 0
        self._failed_tasks = 0
        self._total_retries = 0
        self._latencies_ms.clear()
        self._tool_stats.clear()
        self._guardrail_counts = {"allow": 0, "confirm": 0, "mfa": 0, "block": 0}
        if self.metrics_file.exists():
            try:
                self.metrics_file.unlink()
            except Exception:
                pass


# Global default metrics collector
default_metrics = MetricsCollector()
