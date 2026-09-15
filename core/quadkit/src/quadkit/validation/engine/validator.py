"""Composable field validator with ``Result`` output.

Aggregates :class:`~quadkit.validation.rules.Rule` instances per field name
and runs them all at once, collecting every error into a single
:class:`~quadkit.contracts.validation.ValidationError`.

For async validation (e.g. uniqueness DB lookups), use :class:`AsyncValidator`.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, get_type_hints

from quadkit.contracts.exceptions.domain import FieldError, ValidationError
from quadkit.result import Err, Ok, Result
from quadkit.validation.config import ValidationConfig
from quadkit.validation.engine.coercion import coerce_field_value
from quadkit.validation.rules import AbstractAsyncRule, AbstractRule

T = TypeVar("T")


class ValidatorImpl(Generic[T]):
    """Composable field validation with ``Result`` output.

    Example::

        v = (
            ValidatorImpl()
            .rule("name", required(), min_length(2))
            .rule("email", required(), email_format())
        )
        result = v.validate({"name": "Jo", "email": "jo@example.com"})
    """

    def __init__(
        self,
        stop_on_first_error: bool = False,
        coerce_types: bool = False,
    ) -> None:
        self._rules: dict[str, list[AbstractRule[Any]]] = {}
        self._stop_on_first_error = stop_on_first_error
        self._coerce_types = coerce_types

    @classmethod
    def from_config(cls, config: ValidationConfig) -> ValidatorImpl[T]:
        """Create a validator from a :class:`ValidationConfig`.

        Consumes ``config.stop_on_first_error`` and ``config.coerce_types``.
        """
        return cls(
            stop_on_first_error=config.stop_on_first_error,
            coerce_types=config.coerce_types,
        )

    # ------------------------------------------------------------------
    # Builder API
    # ------------------------------------------------------------------

    def rule(self, field: str, *rules: AbstractRule[Any]) -> ValidatorImpl[T]:
        """Register one or more validation rules for *field*.

        Returns ``self`` so calls can be chained.
        """
        self._rules.setdefault(field, []).extend(rules)
        return self

    # ------------------------------------------------------------------
    # Validation API
    # ------------------------------------------------------------------

    def validate(self, data: dict[str, Any]) -> Result[dict[str, Any], ValidationError]:
        """Run all registered rules against *data* and return a ``Result``.

        Every field is checked even if an earlier field already failed so
        the caller receives *all* errors at once.
        """
        errors: list[FieldError] = []
        for field_name, rules in self._rules.items():
            value = data.get(field_name)
            for r in rules:
                result = r(value, field_name)
                if result.is_err():
                    errors.append(result.unwrap_err())
                    break  # stop on first failure per field
            if errors and self._stop_on_first_error:
                break  # stop on first failure across fields
        if errors:
            return Err(ValidationError(errors=errors))
        return Ok(data)

    def validate_object(self, obj: Any) -> Result[Any, ValidationError]:
        """Validate an object by reading attributes via ``getattr``.

        Behaves identically to :meth:`validate` but extracts values from
        the object instead of a dict. When constructed with
        ``coerce_types=True``, attribute values are coerced against the
        object's type annotations (``bool``/``int``/``float``/``UUID``/
        ``datetime``/``Enum``/model) before validation.
        """
        try:
            type_hints = get_type_hints(type(obj))
        except Exception:  # noqa: S112 — unresolved hints fall back to raw
            type_hints = getattr(type(obj), "__annotations__", {})
        data: dict[str, Any] = {}
        for field_name in self._rules:
            value = getattr(obj, field_name, None)
            if self._coerce_types:
                value = coerce_field_value(field_name, value, type_hints, None)
            data[field_name] = value
        result = self.validate(data)
        if result.is_ok():
            return Ok(obj)
        return result

    def is_valid(self, data: dict[str, Any]) -> bool:
        """Quick boolean validity check."""
        return self.validate(data).is_ok()


class AsyncValidator(Generic[T]):
    """Composable async field validator with ``Result`` output.

    Mirrors :class:`ValidatorImpl` but supports :class:`~quadkit.validation.rules.AsyncRule`
    instances alongside regular :class:`~quadkit.validation.rules.Rule` instances.

    Example::

        validator = AsyncValidator()
        validator.add("email", required(), AsyncUniqueEmail(user_repo))
        result = await validator.validate({"email": "a@b.com"})
    """

    def __init__(
        self,
        stop_on_first_error: bool = False,
        coerce_types: bool = False,
    ) -> None:
        self._rules: dict[str, list[AbstractRule | AbstractAsyncRule]] = {}
        self._stop_on_first_error = stop_on_first_error
        self._coerce_types = coerce_types

    @classmethod
    def from_config(cls, config: ValidationConfig) -> AsyncValidator[T]:
        """Create a validator from a :class:`ValidationConfig`.

        Consumes ``config.stop_on_first_error`` and ``config.coerce_types``.
        """
        return cls(
            stop_on_first_error=config.stop_on_first_error,
            coerce_types=config.coerce_types,
        )

    def rule(
        self, field_name: str, *rules: AbstractRule | AbstractAsyncRule
    ) -> AsyncValidator[T]:
        """Register *rules* for *field_name*. Returns self for chaining."""
        self._rules.setdefault(field_name, []).extend(rules)
        return self

    def add(
        self, field_name: str, *rules: AbstractRule | AbstractAsyncRule
    ) -> AsyncValidator[T]:
        """Alias for :meth:`rule`. Prefer ``rule()`` for API consistency."""
        return self.rule(field_name, *rules)

    async def validate(
        self, data: dict[str, Any]
    ) -> Result[dict[str, Any], ValidationError]:
        """Validate *data* asynchronously, running all sync and async rules.

        Args:
            data: Mapping of field names to values to validate.

        Returns:
            ``Ok(data)`` on success or ``Err(ValidationError)`` with all errors.
        """

        errors: list[FieldError] = []
        for field_name, rules in self._rules.items():
            value = data.get(field_name)
            for rule in rules:
                if isinstance(rule, AbstractAsyncRule):
                    result = await rule(value, field_name)
                else:
                    result = rule(value, field_name)
                if result.is_err():
                    errors.append(result.unwrap_err())
                    break
            if errors and self._stop_on_first_error:
                break  # stop on first failure across fields
        if errors:
            return Err(ValidationError(errors=errors))
        return Ok(data)

    async def validate_object(self, obj: Any) -> Result[Any, ValidationError]:
        """Validate an object by reading attributes via ``getattr``.

        Args:
            obj: Object whose attributes are validated. When constructed
                with ``coerce_types=True``, attribute values are coerced
                against the object's type annotations before validation.

        Returns:
            ``Ok(obj)`` on success or ``Err(ValidationError)`` with all errors.
        """
        try:
            type_hints = get_type_hints(type(obj))
        except Exception:  # noqa: S112 — unresolved hints fall back to raw
            type_hints = getattr(type(obj), "__annotations__", {})
        data: dict[str, Any] = {}
        for field_name in self._rules:
            value = getattr(obj, field_name, None)
            if self._coerce_types:
                value = coerce_field_value(field_name, value, type_hints, None)
            data[field_name] = value
        result = await self.validate(data)
        if result.is_ok():
            return Ok(obj)
        return result


__all__ = ["AsyncValidator", "ValidatorImpl"]
