"""Distributed ReAct execution tracer with timing spans and waterfall trees (Feature 109)."""

from __future__ import annotations

import contextvars
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from firefly.memory.redactor import SecretRedactor


@dataclass
class TraceSpan:
    """An individual timed operation span within an execution trace."""

    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: float = 0.0
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "OK"  # "OK" or "ERROR"

    def end(self, status: str = "OK") -> None:
        """Finishes the span and computes duration."""
        self.end_time = time.monotonic()
        self.duration_ms = (self.end_time - self.start_time) * 1000.0
        self.status = status

    def add_event(self, name: str, data: Optional[Dict[str, Any]] = None) -> None:
        """Records an internal point-in-time event inside this span."""
        self.events.append(
            {
                "name": name,
                "timestamp": time.time(),
                "data": data or {},
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_active_span: contextvars.ContextVar[Optional[TraceSpan]] = contextvars.ContextVar(
    "_active_span", default=None
)


class Tracer:
    """Manages hierarchical execution tracing for ReAct loops, tools, and reflection."""

    def __init__(self) -> None:
        self._completed_spans: List[TraceSpan] = []

    def get_current_span(self) -> Optional[TraceSpan]:
        """Returns the currently active span in this async context."""
        return _active_span.get()

    class _SpanContext:
        def __init__(self, span: TraceSpan, tracer: Tracer):
            self.span = span
            self.tracer = tracer
            self.token: Optional[contextvars.Token[Optional[TraceSpan]]] = None

        def __enter__(self) -> TraceSpan:
            self.token = _active_span.set(self.span)
            return self.span

        def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
            status = "ERROR" if exc_type else "OK"
            self.span.end(status=status)
            self.tracer._completed_spans.append(self.span)
            if self.token:
                _active_span.reset(self.token)

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> _SpanContext:
        """Context manager starting a new timed span."""
        parent = self.get_current_span()
        t_id = trace_id or (parent.trace_id if parent else f"trc_{uuid.uuid4().hex[:12]}")
        p_id = parent_span_id or (parent.span_id if parent else None)

        # Sanitize attributes of secrets
        clean_attrs: Dict[str, Any] = {}
        if attributes:
            for k, v in attributes.items():
                if isinstance(v, str):
                    clean_attrs[k] = SecretRedactor.redact(v)
                else:
                    clean_attrs[k] = v

        span = TraceSpan(
            trace_id=t_id,
            span_id=f"spn_{uuid.uuid4().hex[:8]}",
            parent_span_id=p_id,
            name=name,
            start_time=time.monotonic(),
            attributes=clean_attrs,
        )
        return self._SpanContext(span, self)

    def record_step(
        self,
        step_idx: int,
        thought: str,
        action: str,
        observation: str,
        duration_ms: float,
    ) -> TraceSpan:
        """Helper to record a finished ReAct step."""
        now = time.monotonic()
        span = TraceSpan(
            trace_id=f"trc_step_{step_idx}",
            span_id=f"spn_{uuid.uuid4().hex[:8]}",
            parent_span_id=None,
            name=f"ReAct.Step_{step_idx}",
            start_time=now - (duration_ms / 1000.0),
            end_time=now,
            duration_ms=duration_ms,
            attributes={
                "step": step_idx,
                "thought": SecretRedactor.redact(thought),
                "action": SecretRedactor.redact(action),
                "observation": SecretRedactor.redact(observation[:300]),
            },
        )
        self._completed_spans.append(span)
        return span

    def get_spans(self) -> List[TraceSpan]:
        """Returns all recorded spans."""
        return list(self._completed_spans)

    def format_waterfall(self) -> str:
        """Renders an ASCII/text waterfall timeline for recorded spans."""
        if not self._completed_spans:
            return "No trace spans recorded."

        lines = ["🐾 Firefly Execution Trace Waterfall:"]
        for span in self._completed_spans:
            status_icon = "✔" if span.status == "OK" else "✘"
            bar_len = min(40, max(1, int(span.duration_ms / 20.0)))
            bar = "■" * bar_len
            indent = "  " if span.parent_span_id else ""
            lines.append(
                f"{indent}[{status_icon}] {span.name:<25} {span.duration_ms:>7.1f}ms  {bar}"
            )
            if "thought" in span.attributes:
                t_snip = span.attributes["thought"][:60]
                lines.append(f"{indent}    💭 thought: {t_snip}")
            if "action" in span.attributes:
                a_snip = span.attributes["action"][:60]
                lines.append(f"{indent}    ⚡ action:  {a_snip}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clears all accumulated spans."""
        self._completed_spans.clear()


# Global default tracer
default_tracer = Tracer()
