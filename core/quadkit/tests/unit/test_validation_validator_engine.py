"""Tests for the composable Validator / AsyncValidator engines."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.exceptions.domain import FieldError
from quadkit.result import Err, Ok
from quadkit.validation.config import ValidationConfig
from quadkit.validation.engine.validator import AsyncValidator, ValidatorImpl
from quadkit.validation.rules import (
    AbstractAsyncRule,
    Custom,
    email_format,
    max_length,
    min_length,
    required,
)


def _validator(**kw: Any) -> ValidatorImpl[Any]:
    v = ValidatorImpl(**kw)
    return v.rule("name", required(), min_length(2)).rule(
        "code", required(), max_length(5)
    )


class TestValidatorImpl:
    def test_valid_data(self) -> None:
        result = _validator().validate({"name": "Jo", "code": "AB"})
        assert result.is_ok()
        assert result.unwrap() == {"name": "Jo", "code": "AB"}

    def test_collects_all_field_errors(self) -> None:
        result = _validator().validate({"name": "J", "code": "TOOLONG"})
        assert result.is_err()
        errors = result.unwrap_err().errors
        assert len(errors) == 2
        assert {e.field for e in errors} == {"name", "code"}

    def test_stops_at_first_rule_failure_per_field(self) -> None:
        v = ValidatorImpl().rule("x", required(), required(), max_length(1))
        result = v.validate({"x": ""})
        errors = result.unwrap_err().errors
        # Two required rules would both fail, but only the first is recorded.
        assert len(errors) == 1

    def test_stop_on_first_error_across_fields(self) -> None:
        v = _validator(stop_on_first_error=True)
        result = v.validate({"name": "J", "code": "TOOLONG"})
        errors = result.unwrap_err().errors
        assert len(errors) == 1

    def test_missing_field_treated_as_none(self) -> None:
        result = _validator().validate({})
        errors = result.unwrap_err().errors
        assert {e.field for e in errors} == {"name", "code"}

    def test_is_valid(self) -> None:
        v = _validator()
        assert v.is_valid({"name": "Jo", "code": "AB"}) is True
        assert v.is_valid({"name": ""}) is False

    def test_rule_chaining_returns_self(self) -> None:
        v = ValidatorImpl()
        assert v.rule("a", required()) is v

    def test_from_config(self) -> None:
        v = ValidatorImpl.from_config(
            ValidationConfig(stop_on_first_error=True, coerce_types=True)
        )
        assert v._stop_on_first_error is True  # noqa: SLF001
        assert v._coerce_types is True  # noqa: SLF001

    def test_validate_object(self) -> None:
        class Model:
            name: str
            code: str

            def __init__(self) -> None:
                self.name = "Jo"
                self.code = "AB"

        result = _validator().validate_object(Model())
        assert result.is_ok()
        assert result.unwrap().name == "Jo"

    def test_validate_object_failure(self) -> None:
        class Model:
            name: str
            code: str

            def __init__(self) -> None:
                self.name = ""
                self.code = "AB"

        result = _validator().validate_object(Model())
        assert result.is_err()

    def test_validate_object_missing_attribute_is_none(self) -> None:
        class Model:
            pass

        result = _validator().validate_object(Model())
        errors = result.unwrap_err().errors
        assert {e.field for e in errors} == {"name", "code"}

    def test_validate_object_coercion(self) -> None:
        class Model:
            count: int
            flag: bool

            def __init__(self) -> None:
                self.count = "42"  # string from env
                self.flag = "on"

        v = ValidatorImpl(coerce_types=True).rule(
            "count", Custom(lambda x: x > 40, "count too small")
        )
        result = v.validate_object(Model())
        assert result.is_ok()
        # Coercion is applied to the extracted value (not mutated in place).

    def test_validate_object_coercion_invalid_bool(self) -> None:
        class Model:
            flag: bool

            def __init__(self) -> None:
                self.flag = "garbage"

        v = ValidatorImpl(coerce_types=True).rule("flag", required())
        with pytest.raises(ValueError, match="Cannot coerce"):
            v.validate_object(Model())


class _UniqueAsync(AbstractAsyncRule[Any]):
    """Async rule: fails when value is in a blocked set."""

    def __init__(self, blocked: set[str]) -> None:
        self._blocked = blocked

    async def __call__(self, value: Any, field_name: str) -> Any:
        if value in self._blocked:
            return Err(
                FieldError(field=field_name, message=f"{field_name} taken", code="unique"),
            )
        return Ok(value)


class TestAsyncValidator:
    async def test_mixed_sync_async_rules(self) -> None:
        v = AsyncValidator().rule("email", required(), _UniqueAsync({"taken@x.com"}))
        ok = await v.validate({"email": "free@x.com"})
        assert ok.is_ok()

        bad = await v.validate({"email": "taken@x.com"})
        assert bad.is_err()
        assert bad.unwrap_err().errors[0].code == "unique"

    async def test_async_rule_failure(self) -> None:
        v = AsyncValidator().rule("email", _UniqueAsync({"a@b.c"}))
        result = await v.validate({"email": "a@b.c"})
        assert result.is_err()
        assert "taken" in result.unwrap_err().errors[0].message

    async def test_sync_rule_in_async_validator(self) -> None:
        v = AsyncValidator().rule("name", required())
        result = await v.validate({"name": None})
        assert result.is_err()

    async def test_stop_on_first_error(self) -> None:
        v = (
            AsyncValidator(stop_on_first_error=True)
            .rule("a", required())
            .rule("b", required())
        )
        result = await v.validate({"a": None, "b": None})
        assert len(result.unwrap_err().errors) == 1

    async def test_collects_all_errors(self) -> None:
        v = AsyncValidator().rule("a", required()).rule("b", required())
        result = await v.validate({"a": None, "b": None})
        assert len(result.unwrap_err().errors) == 2

    def test_add_alias(self) -> None:
        v = AsyncValidator()
        assert v.add("x", required()) is v
        assert v.rule("y", required()) is v

    def test_from_config(self) -> None:
        v = AsyncValidator.from_config(ValidationConfig(stop_on_first_error=True))
        assert v._stop_on_first_error is True  # noqa: SLF001

    async def test_validate_object(self) -> None:
        class Model:
            email: str

            def __init__(self) -> None:
                self.email = "ok@x.com"

        v = AsyncValidator().rule("email", required(), email_format())
        result = await v.validate_object(Model())
        assert result.is_ok()

    async def test_validate_object_failure(self) -> None:
        class Model:
            email: str

            def __init__(self) -> None:
                self.email = "not-an-email"

        v = AsyncValidator().rule("email", email_format())
        result = await v.validate_object(Model())
        assert result.is_err()

    async def test_validate_object_coercion(self) -> None:
        class Model:
            count: int

            def __init__(self) -> None:
                self.count = "12"

        v = AsyncValidator(coerce_types=True).rule(
            "count", Custom(lambda x: isinstance(x, int) and x == 12, "not coerced int"),
        )
        result = await v.validate_object(Model())
        assert result.is_ok()
