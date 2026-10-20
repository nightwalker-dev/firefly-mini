"""Lightweight Dependency Injection Container for clean modular composition and testing."""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional, Type, TypeVar

T = TypeVar("T")


class ContainerError(Exception):
    """Raised on DI resolution or binding failure."""


class Container:
    """Manages service registrations, singletons, and factory lifecycles."""

    def __init__(self, parent: Optional[Container] = None) -> None:
        self._lock = threading.RLock()
        self._parent = parent
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, Callable[[Container], Any]] = {}
        self._instances: Dict[str, Any] = {}

    def _key(self, service: Type[Any] | str) -> str:
        if isinstance(service, str):
            return service
        return f"{service.__module__}.{service.__qualname__}"

    def register_instance(self, service: Type[T] | str, instance: T) -> Container:
        """Binds a pre-constructed instance."""
        with self._lock:
            key = self._key(service)
            self._instances[key] = instance
        return self

    def register_singleton(
        self, service: Type[T] | str, factory: Callable[[Container], T]
    ) -> Container:
        """Binds a factory evaluated once on first resolution."""
        with self._lock:
            key = self._key(service)
            self._singletons[key] = factory
            self._instances.pop(key, None)
        return self

    def register_factory(
        self, service: Type[T] | str, factory: Callable[[Container], T]
    ) -> Container:
        """Binds a factory evaluated anew on every resolution."""
        with self._lock:
            key = self._key(service)
            self._factories[key] = factory
        return self

    def resolve(self, service: Type[T] | str) -> T:
        """Resolves a service by Type or string identifier."""
        with self._lock:
            key = self._key(service)

            # 1. Existing instance
            if key in self._instances:
                return self._instances[key]  # type: ignore[no-any-return]

            # 2. Lazy singleton
            if key in self._singletons:
                instance = self._singletons[key](self)
                self._instances[key] = instance
                return instance  # type: ignore[no-any-return]

            # 3. Factory
            if key in self._factories:
                return self._factories[key](self)  # type: ignore[no-any-return]

            # 4. Delegate to parent
            if self._parent is not None:
                return self._parent.resolve(service)

        raise ContainerError(f"No binding found for service '{key}'")

    def resolve_optional(self, service: Type[T] | str) -> Optional[T]:
        """Resolves a service or returns None if unbound."""
        try:
            return self.resolve(service)
        except ContainerError:
            return None

    def create_child(self) -> Container:
        """Creates a scoped child container that inherits bindings but allows local overrides."""
        return Container(parent=self)

    def clear(self) -> None:
        """Clears all bindings and instances."""
        with self._lock:
            self._instances.clear()
            self._singletons.clear()
            self._factories.clear()


default_container = Container()
