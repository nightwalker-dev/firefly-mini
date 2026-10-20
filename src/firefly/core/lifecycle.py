"""Lifecycle Manager: graceful startup, shutdown sequence, and OS signal handling."""

from __future__ import annotations

import asyncio
import inspect
import logging
import signal
import threading
from typing import Any, Callable, Coroutine, List, Union

from firefly.core.events import Event, EventBus, default_bus

log = logging.getLogger("firefly.lifecycle")
Hook = Callable[[], Union[None, Coroutine[Any, Any, None]]]


class LifecycleManager:
    """Orchestrates clean daemon startup and graceful termination on signals."""

    def __init__(self, bus: EventBus = default_bus) -> None:
        self.bus = bus
        self._lock = threading.RLock()
        self._startup_hooks: List[Hook] = []
        self._shutdown_hooks: List[Hook] = []
        self._is_running = False
        self._shutdown_event = threading.Event()

    @property
    def is_running(self) -> bool:
        return self._is_running

    def on_startup(self, hook: Hook) -> None:
        """Registers a hook executed upon system startup."""
        with self._lock:
            self._startup_hooks.append(hook)

    def on_shutdown(self, hook: Hook) -> None:
        """Registers a hook executed on shutdown in reverse registration order."""
        with self._lock:
            self._shutdown_hooks.append(hook)

    def start(self) -> None:
        """Executes startup sequence and attaches signal handlers."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._shutdown_event.clear()

        # Run startup hooks
        for hook in self._startup_hooks:
            try:
                if inspect.iscoroutinefunction(hook):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(hook())
                    except RuntimeError:
                        asyncio.run(hook())
                else:
                    hook()
            except Exception as exc:
                log.warning("Startup hook error: %s", exc)

        self.bus.publish_sync(Event(topic="lifecycle.started", data={"status": "online"}))
        self._attach_signals()

    def _attach_signals(self) -> None:
        # Only attach signal handlers in the main thread
        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    signal.signal(sig, self._handle_signal)
                except (ValueError, OSError):
                    pass

    def _handle_signal(self, signum: int, frame: Any) -> None:
        log.info("Signal %s received; initiating graceful shutdown", signum)
        self.shutdown()

    def shutdown(self) -> None:
        """Executes all registered shutdown hooks cleanly."""
        with self._lock:
            if not self._is_running:
                return
            self._is_running = False
            self._shutdown_event.set()

        self.bus.publish_sync(Event(topic="lifecycle.stopping", data={"status": "offline"}))

        # Run shutdown hooks in reverse order
        for hook in reversed(self._shutdown_hooks):
            try:
                if inspect.iscoroutinefunction(hook):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(hook())
                    except RuntimeError:
                        asyncio.run(hook())
                else:
                    hook()
            except Exception as exc:
                log.warning("Shutdown hook error: %s", exc)

    def wait_for_shutdown(self, timeout: float | None = None) -> bool:
        """Blocks until shutdown is requested."""
        return self._shutdown_event.wait(timeout=timeout)


lifecycle = LifecycleManager()
