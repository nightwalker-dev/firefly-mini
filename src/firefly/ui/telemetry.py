"""Real-time system telemetry engine and Unicode sparkline generator for Firefly Mini."""

from __future__ import annotations

import collections
import time
from dataclasses import dataclass
from typing import Deque, List, Optional

import psutil

from firefly.ui.themes import CyberTheme, theme_manager

SPARKLINE_BARS = [" ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]


def render_sparkline(
    values: List[float],
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    width: Optional[int] = None,
) -> str:
    """Renders a series of numerical values as an 8-level Unicode sparkline string.

    Example: [0, 10, 25, 50, 75, 100] -> "  ▂▄▆█"
    """
    if not values:
        return " " * (width or 8)

    sample = values[-width:] if width else values
    lo = min_val if min_val is not None else (min(sample) if sample else 0.0)
    hi = max_val if max_val is not None else (max(sample) if sample else 100.0)

    if hi <= lo:
        hi = lo + 1.0

    chars = []
    num_levels = len(SPARKLINE_BARS) - 1
    for v in sample:
        clamped = max(lo, min(hi, v))
        norm = (clamped - lo) / (hi - lo)
        idx = int(round(norm * num_levels))
        chars.append(SPARKLINE_BARS[idx])

    result = "".join(chars)
    if width and len(result) < width:
        result = result.rjust(width, SPARKLINE_BARS[0])
    return result


def render_gauge_bar(
    percent: float,
    length: int = 16,
    theme: Optional[CyberTheme] = None,
) -> str:
    """Renders a themed cyberpunk progress gauge (e.g. '████████░░░░ 50.0%')."""
    t = theme or theme_manager.current
    clamped = max(0.0, min(100.0, percent))
    filled_len = int(round((clamped / 100.0) * length))
    empty_len = length - filled_len

    color = t.neon_primary
    if clamped > 85.0:
        color = t.danger_red
    elif clamped > 65.0:
        color = t.accent_amber

    filled_part = f"[{color}]" + "█" * filled_len + "[/]"
    empty_part = f"[{t.border_color}]" + "░" * empty_len + "[/]"
    return f"{filled_part}{empty_part} [{color}]{clamped:5.1f}%[/]"


@dataclass
class TelemetrySnapshot:
    """A point-in-time capture of critical system metrics."""

    timestamp: float
    cpu_percent: float
    cpu_count: int
    memory_percent: float
    memory_used_mb: int
    memory_total_mb: int
    swap_percent: float
    disk_percent: float
    disk_free_gb: float
    net_rx_kbs: float
    net_tx_kbs: float


class TelemetryHistory:
    """Maintains sliding-window historical metrics for sparkline visualization."""

    def __init__(self, max_points: int = 30):
        self.max_points = max_points
        self.cpu_history: Deque[float] = collections.deque(maxlen=max_points)
        self.mem_history: Deque[float] = collections.deque(maxlen=max_points)
        self.net_rx_history: Deque[float] = collections.deque(maxlen=max_points)
        self.net_tx_history: Deque[float] = collections.deque(maxlen=max_points)
        self._last_net = psutil.net_io_counters()
        self._last_time = time.time()

    def sample(self) -> TelemetrySnapshot:
        """Collects latest metrics and appends to rolling sparkline buffers."""
        now = time.time()
        dt = max(0.1, now - self._last_time)

        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage("/")

        net = psutil.net_io_counters()
        rx_kbs = max(0.0, ((net.bytes_recv - self._last_net.bytes_recv) / dt) / 1024.0)
        tx_kbs = max(0.0, ((net.bytes_sent - self._last_net.bytes_sent) / dt) / 1024.0)

        self._last_net = net
        self._last_time = now

        self.cpu_history.append(cpu)
        self.mem_history.append(mem.percent)
        self.net_rx_history.append(rx_kbs)
        self.net_tx_history.append(tx_kbs)

        return TelemetrySnapshot(
            timestamp=now,
            cpu_percent=cpu,
            cpu_count=psutil.cpu_count() or 1,
            memory_percent=mem.percent,
            memory_used_mb=int(mem.used // (1024 * 1024)),
            memory_total_mb=int(mem.total // (1024 * 1024)),
            swap_percent=swap.percent,
            disk_percent=disk.percent,
            disk_free_gb=round(disk.free / (1024**3), 1),
            net_rx_kbs=rx_kbs,
            net_tx_kbs=tx_kbs,
        )

    def get_cpu_sparkline(self, width: int = 16) -> str:
        return render_sparkline(list(self.cpu_history), min_val=0.0, max_val=100.0, width=width)

    def get_mem_sparkline(self, width: int = 16) -> str:
        return render_sparkline(list(self.mem_history), min_val=0.0, max_val=100.0, width=width)

    def get_net_rx_sparkline(self, width: int = 16) -> str:
        vals = list(self.net_rx_history)
        hi = max(vals) if vals and max(vals) > 10.0 else 100.0
        return render_sparkline(vals, min_val=0.0, max_val=hi, width=width)

    def get_net_tx_sparkline(self, width: int = 16) -> str:
        vals = list(self.net_tx_history)
        hi = max(vals) if vals and max(vals) > 10.0 else 100.0
        return render_sparkline(vals, min_val=0.0, max_val=hi, width=width)


telemetry_engine = TelemetryHistory()
