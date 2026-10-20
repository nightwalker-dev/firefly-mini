"""Central Event Bus (pub/sub) for clean decoupling between HUD, logger, voice, and agent."""

from __future__ import annotations

import asyncio
import inspect
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Dict, List, Optional, Union

Handler = Callable[[Any], Union[None, Coroutine[Any, Any, None]]]


@dataclass
class Event:
    """Base event payload carrying metadata and timestamp."""

    topic: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    source: str = "core"


class EventBus:
    """Thread-safe publish/subscribe event dispatcher supporting sync and async listeners."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: Dict[str, List[Handler]] = {}
        self._history: List[Event] = []
        self._history_limit = 200

    def subscribe(self, topic: str, handler: Handler) -> Callable[[], None]:
        """Subscribes handler to a topic. Supports wildcards ('*' or 'prefix.*'). Returns unsubscriber."""
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            if handler not in self._subscribers[topic]:
                self._subscribers[topic].append(handler)

        def unsubscribe() -> None:
            self.unsubscribe(topic, handler)

        return unsubscribe

    def unsubscribe(self, topic: str, handler: Handler) -> None:
        """Removes a handler from a topic."""
        with self._lock:
            if topic in self._subscribers and handler in self._subscribers[topic]:
                self._subscribers[topic].remove(handler)
                if not self._subscribers[topic]:
                    del self._subscribers[topic]

    def _matches(self, pattern: str, topic: str) -> bool:
        if pattern == "*" or pattern == topic:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return topic.startswith(prefix + ".") or topic == prefix
        return False

    def publish_sync(self, event: Event) -> None:
        """Publishes an event synchronously to all registered listeners."""
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_limit:
                self._history.pop(0)

            matching_handlers: List[Handler] = []
            for pattern, handlers in self._subscribers.items():
                if self._matches(pattern, event.topic):
                    matching_handlers.extend(handlers)

        for handler in matching_handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    # Handle async listener in sync context
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(handler(event))
                    except RuntimeError:
                        asyncio.run(handler(event))
                else:
                    handler(event)
            except Exception:
                pass  # Listeners must never crash the bus

    async def publish(self, event: Event) -> None:
        """Publishes an event asynchronously."""
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_limit:
                self._history.pop(0)

            matching_handlers: List[Handler] = []
            for pattern, handlers in self._subscribers.items():
                if self._matches(pattern, event.topic):
                    matching_handlers.extend(handlers)

        for handler in matching_handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    handler(event)
            except Exception:
                pass

    def get_history(self, topic_filter: Optional[str] = None) -> List[Event]:
        """Returns recent events recorded by the bus."""
        with self._lock:
            if not topic_filter:
                return list(self._history)
            return [e for e in self._history if self._matches(topic_filter, e.topic)]

    def clear(self) -> None:
        """Clears all subscribers and history (useful in test teardown)."""
        with self._lock:
            self._subscribers.clear()
            self._history.clear()


default_bus = EventBus()
