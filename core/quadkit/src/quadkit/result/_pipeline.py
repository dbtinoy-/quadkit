"""ResultPipeline — fluent chaining API for Result operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Generic, Never, TypeVar, cast

from quadkit.result.types import Ok, Result

if TYPE_CHECKING:
    from collections.abc import Callable

E = TypeVar("E")
F = TypeVar("F")
T = TypeVar("T")
U = TypeVar("U")


class ResultPipeline(Generic[T, E]):
    """Pipeline for chaining Result operations with a fluent, type-safe API.

    The error type ``E`` is preserved through the entire chain so mypy
    can verify error handling at every step.  Use :func:`pipeline` to
    start a pipeline from an infallible initial value.
    """

    __slots__ = ("_result",)

    def __init__(self, initial: Result[T, E]) -> None:
        self._result = initial

    def then(self, func: Callable[[T], Result[U, E]]) -> ResultPipeline[U, E]:
        """Chain a function that returns a Result, preserving the error type."""
        if self._result.is_ok():
            return ResultPipeline(func(self._result.unwrap()))
        return cast("ResultPipeline[U, E]", self)

    def map(self, func: Callable[[T], U]) -> ResultPipeline[U, E]:
        """Apply a function to the value if Ok, preserving the error type."""
        if self._result.is_ok():
            return ResultPipeline(Ok(func(self._result.unwrap())))
        return cast("ResultPipeline[U, E]", self)

    def recover(self, func: Callable[[E], Result[T, F]]) -> ResultPipeline[T, F]:
        """Recover from an error by applying a function that may produce a new error type."""
        if self._result.is_err():
            return ResultPipeline(func(self._result.unwrap_err()))
        return cast("ResultPipeline[T, F]", self)

    def finalize(self) -> Result[T, E]:
        """Get the final typed Result."""
        return self._result


def pipeline(initial: T) -> ResultPipeline[T, Never]:
    """Start a Result pipeline with an infallible initial value.

    The ``Never`` error type signals that no error has been introduced
    yet; the error type is inferred once ``.then()`` or ``.recover()``
    introduces a typed failure.
    """
    return ResultPipeline(Ok(initial))


__all__ = [
    "ResultPipeline",
    "pipeline",
]
