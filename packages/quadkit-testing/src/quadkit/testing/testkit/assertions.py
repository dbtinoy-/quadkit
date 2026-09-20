"""Result assertion helpers for unit tests.

Provides explicit, informative assertions for ``Result[T, E]`` values so test
failures include context about the actual value or error.

Example::

    from quadkit.testing.testkit.assertions import assert_ok, assert_err_type

    result = await service.find_user("123")
    user = assert_ok(result)                         # returns unwrapped value

    result = await service.find_user("missing")
    assert_err_type(result, UserNotFoundError)        # checks error type
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from quadkit.result import Result

T = TypeVar("T")
E = TypeVar("E")


def assert_ok(result: Result[T, E]) -> T:
    """Assert that *result* is ``Ok`` and return its inner value.

    Args:
        result: A ``Result`` instance.

    Returns:
        The unwrapped success value.

    Raises:
        AssertionError: If *result* is ``Err``, with the error included.
    """
    assert result.is_ok(), f"Expected Ok but got Err: {result.unwrap_err()!r}"
    return result.unwrap()


def assert_err(result: Result[Any, E]) -> E:
    """Assert that *result* is ``Err`` and return its inner error.

    Args:
        result: A ``Result`` instance.

    Returns:
        The unwrapped error value.

    Raises:
        AssertionError: If *result* is ``Ok``, with the value included.
    """
    assert result.is_err(), f"Expected Err but got Ok: {result.unwrap()!r}"
    return result.unwrap_err()


def assert_err_type(result: Result[Any, E], error_type: type[E]) -> E:
    """Assert that *result* is ``Err`` with an error of *error_type*.

    Args:
        result: A ``Result`` instance.
        error_type: The expected exception or error class.

    Returns:
        The unwrapped error value.

    Raises:
        AssertionError: If *result* is ``Ok`` or the error is the wrong type.
    """
    error = assert_err(result)
    assert isinstance(error, error_type), (
        f"Expected error of type {error_type.__name__!r}, "
        f"got {type(error).__name__!r}: {error!r}"
    )
    return error


def assert_err_contains(result: Result[Any, E], substring: str) -> E:
    """Assert that *result* is ``Err`` whose string representation contains *substring*.

    Args:
        result: A ``Result`` instance.
        substring: Text that must appear in ``str(error)``.

    Returns:
        The unwrapped error value.

    Raises:
        AssertionError: If *result* is ``Ok`` or the error message lacks *substring*.
    """
    error = assert_err(result)
    assert substring in str(error), (
        f"Expected error message to contain {substring!r}, got {str(error)!r}"
    )
    return error


__all__ = [
    "assert_err",
    "assert_err_contains",
    "assert_err_type",
    "assert_ok",
]
