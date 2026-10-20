"""Generic Result[T, E] pattern for explicit, typed error handling without unhandled exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, NoReturn, TypeVar, Union

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")
F = TypeVar("F")


class UnwrapError(Exception):
    """Raised when unwrapping an Err variant."""


@dataclass(frozen=True)
class Ok(Generic[T]):
    """Successful computation carrying a value of type T."""

    _value: T

    @property
    def value(self) -> T:
        return self._value

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self._value

    def unwrap_or(self, default: Any) -> T:
        return self._value

    def unwrap_err(self) -> NoReturn:
        raise UnwrapError(f"Called unwrap_err on Ok({self._value!r})")

    def map(self, fn: Callable[[T], U]) -> Result[U, Any]:
        return Ok(fn(self._value))

    def map_err(self, fn: Callable[[Any], Any]) -> Result[T, Any]:
        return self

    def and_then(self, fn: Callable[[T], Result[U, E]]) -> Result[U, E]:
        return fn(self._value)

    def __repr__(self) -> str:
        return f"Ok({self._value!r})"


@dataclass(frozen=True)
class Err(Generic[E]):
    """Failed computation carrying an error of type E."""

    _error: E

    @property
    def error(self) -> E:
        return self._error

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> NoReturn:
        if isinstance(self._error, Exception):
            raise UnwrapError(f"Called unwrap on Err({self._error!r})") from self._error
        raise UnwrapError(f"Called unwrap on Err({self._error!r})")

    def unwrap_or(self, default: T) -> T:
        return default

    def unwrap_err(self) -> E:
        return self._error

    def map(self, fn: Callable[[Any], Any]) -> Result[Any, E]:
        return self

    def map_err(self, fn: Callable[[E], F]) -> Result[Any, F]:
        return Err(fn(self._error))

    def and_then(self, fn: Callable[[Any], Any]) -> Result[Any, E]:
        return self

    def __repr__(self) -> str:
        return f"Err({self._error!r})"


Result = Union[Ok[T], Err[E]]


def run_result(fn: Callable[..., T], *args: Any, **kwargs: Any) -> Result[T, Exception]:
    """Executes a callable, returning Ok(value) on success or Err(exception) on error."""
    try:
        return Ok(fn(*args, **kwargs))
    except Exception as exc:
        return Err(exc)
