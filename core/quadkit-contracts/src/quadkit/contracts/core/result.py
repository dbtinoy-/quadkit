"""Result type — concrete Ok/Err implementation.

Canonical location for Result[T, E], Ok, and Err.
All Quadkit packages import from here.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar, cast

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")
F = TypeVar("F")


class UnwrapError(Exception):
    """Raised when unwrap() or unwrap_err() is called on the wrong variant.

    Provides a clearer error type than the generic ``ValueError`` so callers
    can catch it explicitly when needed.
    """

    _code: str = "QK_ERR_RESULT_002"

    def __init__(self, message: str, result: Any | None = None) -> None:
        """Initialise the error.

        Args:
            message: Human-readable description of what was attempted.
            result: The ``Result`` instance that caused the error (optional).
        """
        super().__init__(message)
        self.result = result


class Result(Generic[T, E]):
    """Base Result type. Not abstract — Ok and Err are the only variants."""

    __slots__ = ()

    def is_ok(self) -> bool:
        raise NotImplementedError

    def is_err(self) -> bool:
        raise NotImplementedError

    def unwrap(self) -> T:
        raise NotImplementedError

    def unwrap_err(self) -> E:
        raise NotImplementedError

    def unwrap_or(self, default: T) -> T:
        raise NotImplementedError

    def unwrap_or_else(self, op: Callable[[E], T]) -> T:
        raise NotImplementedError

    def map_sync(self, op: Callable[[T], U]) -> Result[U, E]:
        raise NotImplementedError

    def map_err(self, op: Callable[[E], F]) -> Result[T, F]:
        raise NotImplementedError

    def and_then_sync(self, op: Callable[[T], Result[U, E]]) -> Result[U, E]:
        raise NotImplementedError

    def or_else_sync(self, op: Callable[[E], Result[T, F]]) -> Result[T, F]:
        raise NotImplementedError

    def expect(self, message: str) -> T:
        raise NotImplementedError

    def match(self, ok: Callable[[T], U], err: Callable[[E], U]) -> U:
        raise NotImplementedError

    async def map(self, op: Callable[[T], Awaitable[U]]) -> Result[U, E]:
        raise NotImplementedError

    async def and_then(
        self, op: Callable[[T], Awaitable[Result[U, E]]]
    ) -> Result[U, E]:
        raise NotImplementedError

    async def or_else(self, op: Callable[[E], Awaitable[Result[T, F]]]) -> Result[T, F]:
        raise NotImplementedError

    def flatten(self) -> Result[Any, E]:
        raise NotImplementedError

    def filter(self, predicate: Callable[[T], bool], error: E) -> Result[T, E]:
        raise NotImplementedError

    def ok_or(self, default: U) -> T | U:
        raise NotImplementedError

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
        ok_type: type[T] = type(None),  # type: ignore[assignment]
    ) -> Result[T, Exception]:
        """Wrap a caught exception into an Err result."""
        return Err(exc)

    def to_optional(self) -> T | None:
        return self.unwrap() if self.is_ok() else None

    def inspect(self, op: Callable[[T], None]) -> Result[T, E]:
        if self.is_ok():
            op(self.unwrap())
        return self

    def inspect_err(self, op: Callable[[E], None]) -> Result[T, E]:
        if self.is_err():
            op(self.unwrap_err())
        return self


class Ok(Result[T, E]):
    __slots__ = ("_value",)
    __match_args__ = ("_value",)

    def __init__(self, value: T) -> None:
        self._value = value

    def is_ok(self) -> bool:
        return True

    def is_err(self) -> bool:
        return False

    def unwrap(self) -> T:
        return self._value

    def unwrap_err(self) -> E:
        raise UnwrapError(f"Called unwrap_err on Ok({self._value!r})")

    def unwrap_or(self, default: T) -> T:
        return self._value

    def unwrap_or_else(self, op: Callable[[E], T]) -> T:
        return self._value

    def map_sync(self, op: Callable[[T], U]) -> Result[U, E]:
        return Ok(op(self._value))

    def map_err(self, op: Callable[[E], F]) -> Result[T, F]:
        return cast("Result[T, F]", self)

    def and_then_sync(self, op: Callable[[T], Result[U, E]]) -> Result[U, E]:
        return op(self._value)

    def or_else_sync(self, op: Callable[[E], Result[T, F]]) -> Result[T, F]:
        return cast("Result[T, F]", self)

    def expect(self, message: str) -> T:
        return self._value

    def match(self, ok: Callable[[T], U], err: Callable[[E], U]) -> U:
        return ok(self._value)

    async def map(self, op: Callable[[T], Awaitable[U]]) -> Result[U, E]:
        return Ok(await op(self._value))

    async def async_map(self, op: Callable[[T], Awaitable[U]]) -> Result[U, E]:
        """Alias for ``map`` — exists for backward compatibility."""
        return Ok(await op(self._value))

    async def and_then(
        self, op: Callable[[T], Awaitable[Result[U, E]]]
    ) -> Result[U, E]:
        return await op(self._value)

    async def or_else(self, op: Callable[[E], Awaitable[Result[T, F]]]) -> Result[T, F]:
        return cast("Result[T, F]", self)

    def flatten(self) -> Result[Any, E]:
        if isinstance(self._value, Result):
            return self._value
        return cast("Result[Any, E]", self)

    def filter(self, predicate: Callable[[T], bool], error: E) -> Result[T, E]:
        return self if predicate(self._value) else Err(error)

    def ok_or(self, default: U) -> T:
        return self._value

    def __repr__(self) -> str:
        return f"Ok({self._value!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Ok) and self._value == other._value

    def __hash__(self) -> int:
        return hash(("Ok", self._value))


class Err(Result[T, E]):
    __slots__ = ("_error",)
    __match_args__ = ("_error",)

    def __init__(self, error: E) -> None:
        self._error = error

    def is_ok(self) -> bool:
        return False

    def is_err(self) -> bool:
        return True

    def unwrap(self) -> T:
        raise UnwrapError(f"Called unwrap on Err({self._error!r})", self)

    def unwrap_err(self) -> E:
        return self._error

    def unwrap_or(self, default: T) -> T:
        return default

    def unwrap_or_else(self, op: Callable[[E], T]) -> T:
        return op(self._error)

    def map_sync(self, op: Callable[[T], U]) -> Result[U, E]:
        return cast("Result[U, E]", self)

    def map_err(self, op: Callable[[E], F]) -> Result[T, F]:
        return Err(op(self._error))

    def and_then_sync(self, op: Callable[[T], Result[U, E]]) -> Result[U, E]:
        return cast("Result[U, E]", self)

    def or_else_sync(self, op: Callable[[E], Result[T, F]]) -> Result[T, F]:
        return op(self._error)

    def expect(self, message: str) -> T:
        raise UnwrapError(f"{message}: {self._error!r}", self)

    def match(self, ok: Callable[[T], U], err: Callable[[E], U]) -> U:
        return err(self._error)

    async def map(self, op: Callable[[T], Awaitable[U]]) -> Result[U, E]:
        return cast("Result[U, E]", self)

    async def async_map(self, op: Callable[[T], Awaitable[U]]) -> Result[U, E]:
        """Alias for ``map`` — exists for backward compatibility."""
        return cast("Result[U, E]", self)

    async def and_then(
        self, op: Callable[[T], Awaitable[Result[U, E]]]
    ) -> Result[U, E]:
        return cast("Result[U, E]", self)

    async def or_else(self, op: Callable[[E], Awaitable[Result[T, F]]]) -> Result[T, F]:
        return await op(self._error)

    def flatten(self) -> Result[Any, E]:
        return cast("Result[Any, E]", self)

    def filter(self, predicate: Callable[[T], bool], error: E) -> Result[T, E]:
        return self

    def ok_or(self, default: U) -> U:
        return default

    def __repr__(self) -> str:
        return f"Err({self._error!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Err) and self._error == other._error

    def __hash__(self) -> int:
        return hash(("Err", self._error))


__all__ = ["Err", "Ok", "Result", "UnwrapError"]
