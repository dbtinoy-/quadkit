"""Composable validation rule callables.

Each rule is a callable ``(value, field_name) -> Result[Any, FieldError]``
that validates a single field value.  On success the original value is
returned inside ``Ok``; on failure an ``Err`` containing a ``FieldError``
(with ``field``, ``message``, ``code`` attributes) is returned.

Async rules follow the same contract but return a coroutine.
Use :class:`AsyncRule` for I/O-bound checks (e.g. uniqueness DB lookups).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import re
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from quadkit.contracts.exceptions.domain import FieldError
from quadkit.result import Err, Ok, Result
from quadkit.validation.constants import (
    CODE_CUSTOM,
    CODE_EMAIL,
    CODE_MAX_LENGTH,
    CODE_MIN_LENGTH,
    CODE_ONE_OF,
    CODE_PATTERN,
    CODE_RANGE_MAX,
    CODE_RANGE_MIN,
    CODE_REQUIRED,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

T = TypeVar("T")


class AbstractRule(ABC, Generic[T]):
    """Abstract base for all validation rules."""

    @abstractmethod
    def __call__(self, value: Any, field_name: str) -> Result[T, FieldError]:
        """Validate *value* for *field_name* and return a ``Result``."""


# ---------------------------------------------------------------------------
# Concrete rules
# ---------------------------------------------------------------------------


class Required(AbstractRule[Any]):
    """Fail if the value is ``None`` or an empty/blank string."""

    def __call__(self, value: Any, field_name: str) -> Result[Any, FieldError]:
        if value is None or (isinstance(value, str) and not value.strip()):
            return Err(
                FieldError(
                    field=field_name,
                    message=f"{field_name} is required",
                    code=CODE_REQUIRED,
                ),
            )
        return Ok(value)


class MinLength(AbstractRule[str]):
    """Fail if ``len(value) < min_len``."""

    def __init__(self, min_len: int) -> None:
        self._min = min_len

    def __call__(self, value: Any, field_name: str) -> Result[str, FieldError]:
        if value is not None and len(value) < self._min:
            return Err(
                FieldError(
                    field=field_name,
                    message=f"{field_name} must be at least {self._min} characters",
                    code=CODE_MIN_LENGTH,
                ),
            )
        return Ok(value)


class MaxLength(AbstractRule[str]):
    """Fail if ``len(value) > max_len``."""

    def __init__(self, max_len: int) -> None:
        self._max = max_len

    def __call__(self, value: Any, field_name: str) -> Result[str, FieldError]:
        if value is not None and len(value) > self._max:
            return Err(
                FieldError(
                    field=field_name,
                    message=f"{field_name} must be at most {self._max} characters",
                    code=CODE_MAX_LENGTH,
                ),
            )
        return Ok(value)


class Pattern(AbstractRule[str]):
    """Fail if the value does not match the given regex."""

    def __init__(self, regex: str) -> None:
        self._pattern = re.compile(regex)
        self._raw = regex

    def __call__(self, value: Any, field_name: str) -> Result[str, FieldError]:
        if value is not None and not self._pattern.match(str(value)):
            return Err(
                FieldError(
                    field=field_name,
                    message=f"{field_name} does not match pattern {self._raw!r}",
                    code=CODE_PATTERN,
                ),
            )
        return Ok(value)


class Range(AbstractRule[float | None]):
    """Fail if the numeric value is outside ``[min_val, max_val]``."""

    def __init__(
        self,
        min_val: float | None = None,
        max_val: float | None = None,
    ) -> None:
        self._min = min_val
        self._max = max_val

    def __call__(self, value: Any, field_name: str) -> Result[float | None, FieldError]:
        if value is None:
            return Ok(value)
        if self._min is not None and value < self._min:
            return Err(
                FieldError(
                    field=field_name,
                    message=f"{field_name} must be >= {self._min}",
                    code=CODE_RANGE_MIN,
                ),
            )
        if self._max is not None and value > self._max:
            return Err(
                FieldError(
                    field=field_name,
                    message=f"{field_name} must be <= {self._max}",
                    code=CODE_RANGE_MAX,
                ),
            )
        return Ok(value)


class OneOf(AbstractRule[Any]):
    """Fail if the value is not one of the allowed choices."""

    def __init__(self, *choices: Any) -> None:
        self._choices: Sequence[Any] = choices

    def __call__(self, value: Any, field_name: str) -> Result[Any, FieldError]:
        if value is not None and value not in self._choices:
            return Err(
                FieldError(
                    field=field_name,
                    message=(f"{field_name} must be one of {list(self._choices)}"),
                    code=CODE_ONE_OF,
                ),
            )
        return Ok(value)


_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class EmailFormat(AbstractRule[str]):
    """Fail if the value is not a valid email address (basic check)."""

    def __call__(self, value: Any, field_name: str) -> Result[str, FieldError]:
        if value is not None and not _EMAIL_RE.match(str(value)):
            return Err(
                FieldError(
                    field=field_name,
                    message=f"{field_name} is not a valid email address",
                    code=CODE_EMAIL,
                ),
            )
        return Ok(value)


class Custom(AbstractRule[Any]):
    """User-provided predicate wrapped as a validation rule.

    The predicate should return ``True`` when the value is valid.
    """

    def __init__(self, func: Callable[[Any], bool], message: str) -> None:
        self._func = func
        self._message = message

    def __call__(self, value: Any, field_name: str) -> Result[Any, FieldError]:
        if value is not None and not self._func(value):
            return Err(
                FieldError(
                    field=field_name,
                    message=self._message,
                    code=CODE_CUSTOM,
                ),
            )
        return Ok(value)


# ---------------------------------------------------------------------------
# Convenience factory functions
# ---------------------------------------------------------------------------


def required() -> Required:
    """Require a non-empty value."""
    return Required()


def min_length(n: int) -> MinLength:
    """Require at least *n* characters."""
    return MinLength(n)


def max_length(n: int) -> MaxLength:
    """Require at most *n* characters."""
    return MaxLength(n)


def pattern(regex: str) -> Pattern:
    """Require the value to match *regex*."""
    return Pattern(regex)


def range_check(
    min_val: float | None = None,
    max_val: float | None = None,
) -> Range:
    """Require a numeric value within ``[min_val, max_val]``."""
    return Range(min_val, max_val)


def one_of(*choices: Any) -> OneOf:
    """Require the value to be one of the given *choices*."""
    return OneOf(*choices)


def email_format() -> EmailFormat:
    """Require a valid email address."""
    return EmailFormat()


def custom(func: Callable[[Any], bool], message: str) -> Custom:
    """Create a rule from a boolean predicate."""
    return Custom(func, message)


# ---------------------------------------------------------------------------
# Async rules
# ---------------------------------------------------------------------------


class AbstractAsyncRule(ABC, Generic[T]):
    """Abstract base for async validation rules.

    Useful for I/O-bound checks such as database uniqueness lookups.
    The contract mirrors :class:`Rule` but returns a coroutine.

    Example::

        class UniqueEmail(AsyncRule):
            def __init__(self, repo: UserRepository) -> None:
                self._repo = repo

            async def __call__(self, value: Any, field_name: str) -> Result[Any, FieldError]:
                if await self._repo.email_exists(value):
                    return Err(FieldError(field=field_name, message="already taken", code="unique"))
                return Ok(value)
    """

    @abstractmethod
    async def __call__(self, value: Any, field_name: str) -> Result[T, FieldError]:
        """Asynchronously validate *value* for *field_name*."""


# ---------------------------------------------------------------------------
# Result-based helper functions (previously in helpers.py)
# ---------------------------------------------------------------------------


def validate_required(value: T | None, name: str = "value") -> Result[T, ValueError]:
    """Return ``Ok(value)`` if *value* is not ``None``, otherwise ``Err``.

    Args:
        value: Value to check for presence.
        name: Human-readable field name used in the error message.

    Returns:
        ``Ok(value)`` when the value is present, ``Err(ValueError)`` otherwise.
    """
    if value is None:
        return Err(ValueError(f"{name} is required"))
    return Ok(value)


def validate_type(
    value: Any,
    expected_type: type[T],
    name: str = "value",
) -> Result[T, TypeError]:
    """Return ``Ok(value)`` if *value* is an instance of *expected_type*.

    Args:
        value: Value whose type to check.
        expected_type: Exact type (or base class) the value must be an instance of.
        name: Human-readable field name used in the error message.

    Returns:
        ``Ok(value)`` on success, ``Err(TypeError)`` on mismatch.
    """
    if not isinstance(value, expected_type):
        return Err(
            TypeError(
                f"{name} must be of type {expected_type.__name__},"
                f" got {type(value).__name__}",
            ),
        )
    return Ok(value)


def validate_range(
    value: T,
    min_value: T | None = None,
    max_value: T | None = None,
    name: str = "value",
) -> Result[T, ValueError]:
    """Return ``Ok(value)`` if *value* falls within [*min_value*, *max_value*].

    Either bound may be omitted (``None``) to skip that check.

    Args:
        value: Value to validate.
        min_value: Inclusive lower bound, or ``None`` to skip.
        max_value: Inclusive upper bound, or ``None`` to skip.
        name: Human-readable field name used in error messages.

    Returns:
        ``Ok(value)`` when in range, ``Err(ValueError)`` otherwise.
    """
    if min_value is not None and value < min_value:  # type: ignore[operator]
        return Err(ValueError(f"{name} must be at least {min_value}"))
    if max_value is not None and value > max_value:  # type: ignore[operator]
        return Err(ValueError(f"{name} must be at most {max_value}"))
    return Ok(value)
