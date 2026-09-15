"""Tests for validation/validator module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from quadkit.contracts.exceptions.domain import FieldError
from quadkit.result import Err, Ok
from quadkit.validation.engine import AsyncValidator, ValidatorImpl
from quadkit.validation.rules import (
    MinLength,
    Required,
    max_length,
    range_check,
)
from quadkit.validation.rules.rules import AbstractAsyncRule


class TestValidatorCreation:
    """Tests for creating a Validator."""

    def test_empty_validator(self) -> None:
        """Test creating empty validator."""
        v = ValidatorImpl()
        assert v._rules == {}

    def test_validator_rule_chaining(self) -> None:
        """Test that rule() returns self for chaining."""
        v = ValidatorImpl()
        result = v.rule("name", Required())
        assert result is v


class TestValidatorRuleRegistration:
    """Tests for registering rules."""

    def test_single_rule(self) -> None:
        """Test registering single rule."""
        v = ValidatorImpl().rule("name", Required())
        assert "name" in v._rules
        assert len(v._rules["name"]) == 1

    def test_multiple_rules_same_field(self) -> None:
        """Test registering multiple rules for same field."""
        v = ValidatorImpl().rule("name", Required(), MinLength(2))
        assert len(v._rules["name"]) == 2

    def test_multiple_fields(self) -> None:
        """Test registering rules for multiple fields."""
        v = ValidatorImpl().rule("name", Required()).rule("email", Required())
        assert len(v._rules) == 2


class TestValidatorValidate:
    """Tests for validate() method."""

    def test_validate_valid_data(self) -> None:
        """Test validate returns Ok for valid data."""
        v = ValidatorImpl().rule("name", Required())
        result = v.validate({"name": "John"})
        assert result.is_ok()
        assert result.unwrap() == {"name": "John"}

    def test_validate_invalid_data(self) -> None:
        """Test validate returns Err for invalid data."""
        v = ValidatorImpl().rule("name", Required())
        result = v.validate({"name": None})
        assert result.is_err()
        errors = result.unwrap_err().errors
        assert len(errors) == 1
        assert errors[0].field == "name"

    def test_validate_missing_field(self) -> None:
        """Test validate with missing field."""
        v = ValidatorImpl().rule("name", Required())
        result = v.validate({})
        assert result.is_err()

    def test_validate_multiple_fields_all_valid(self) -> None:
        """Test validate with multiple valid fields."""
        v = ValidatorImpl().rule("name", Required()).rule("age", range_check(min_val=0))
        result = v.validate({"name": "John", "age": 25})
        assert result.is_ok()

    def test_validate_multiple_errors(self) -> None:
        """Test validate collects all errors."""
        v = ValidatorImpl().rule("name", Required()).rule("age", range_check(min_val=0))
        result = v.validate({"name": None, "age": -5})
        assert result.is_err()
        errors = result.unwrap_err().errors
        assert len(errors) == 2


class TestValidatorValidateObject:
    """Tests for validate_object() method."""

    def test_validate_object_valid(self) -> None:
        """Test validate_object with valid object."""
        v = ValidatorImpl().rule("name", Required())

        @dataclass
        class Person:
            name: str = "John"

        result = v.validate_object(Person())
        assert result.is_ok()

    def test_validate_object_invalid(self) -> None:
        """Test validate_object with invalid object."""
        v = ValidatorImpl().rule("name", Required())

        @dataclass
        class Person:
            name: str | None = None

        result = v.validate_object(Person())
        assert result.is_err()


class TestValidatorStopsOnFirstError:
    """Tests for first-error-per-field behavior."""

    def test_stops_on_first_error(self) -> None:
        """Test that validation stops on first error per field."""
        # This test verifies the break statement behavior
        v = ValidatorImpl().rule("name", Required(), MinLength(2), max_length(10))
        # If the first rule (Required) fails, others aren't checked
        result = v.validate({"name": None})
        assert result.is_err()
        # Only one error because it breaks on first failure
        errors = result.unwrap_err().errors
        assert len(errors) == 1


class TestValidatorEdgeCases:
    """Tests for edge cases."""

    def test_validate_empty_rules(self) -> None:
        """Test validate with no rules."""
        v = ValidatorImpl()
        result = v.validate({"any": "data"})
        assert result.is_ok()

    def test_validate_field_not_in_rules(self) -> None:
        """Test validate ignores fields not in rules."""
        v = ValidatorImpl().rule("name", Required())
        result = v.validate({"name": "John", "extra": "ignored"})
        assert result.is_ok()

    def test_validate_none_value_for_missing_field(self) -> None:
        """Test validate handles None for missing field values."""
        v = ValidatorImpl().rule("optional", MinLength(2))
        result = v.validate({"optional": None})
        # MinLength passes for None (not required)
        assert result.is_ok()


class TestValidatorAdditionalRules:
    """Tests for additional validation rules."""

    def test_email_format_passes(self) -> None:
        """Test email_format rule passes with valid email."""
        from quadkit.validation.rules import email_format

        v = ValidatorImpl().rule("email", email_format())
        result = v.validate({"email": "test@example.com"})
        assert result.is_ok()

    def test_email_format_fails(self) -> None:
        """Test email_format rule fails with invalid email."""
        from quadkit.validation.rules import email_format

        v = ValidatorImpl().rule("email", email_format())
        result = v.validate({"email": "invalid-email"})
        assert result.is_err()

    def test_pattern_passes(self) -> None:
        """Test pattern rule passes with matching value."""
        from quadkit.validation.rules import pattern

        v = ValidatorImpl().rule("code", pattern(r"^[A-Z]{3}$"))
        result = v.validate({"code": "ABC"})
        assert result.is_ok()

    def test_pattern_fails(self) -> None:
        """Test pattern rule fails with non-matching value."""
        from quadkit.validation.rules import pattern

        v = ValidatorImpl().rule("code", pattern(r"^[A-Z]{3}$"))
        result = v.validate({"code": "abc"})
        assert result.is_err()

    def test_one_of_passes(self) -> None:
        """Test one_of rule passes when value is in list."""
        from quadkit.validation.rules import one_of

        v = ValidatorImpl().rule("status", one_of("active", "inactive"))
        result = v.validate({"status": "active"})
        assert result.is_ok()

    def test_one_of_fails(self) -> None:
        """Test one_of rule fails when value is not in list."""
        from quadkit.validation.rules import one_of

        v = ValidatorImpl().rule("status", one_of("active", "inactive"))
        result = v.validate({"status": "pending"})
        assert result.is_err()

    def test_custom_rule_passes(self) -> None:
        """Test custom rule passes when predicate returns True."""
        from quadkit.validation.rules import custom

        v = ValidatorImpl().rule("value", custom(bool, "Invalid value"))
        result = v.validate({"value": "valid"})
        assert result.is_ok()

    def test_custom_rule_fails(self) -> None:
        """Test custom rule fails when predicate returns False."""
        from quadkit.validation.rules import custom

        v = ValidatorImpl().rule("value", custom(bool, "Invalid value"))
        result = v.validate({"value": ""})
        assert result.is_err()

    def test_is_valid_true(self) -> None:
        """Test is_valid returns True for valid data."""
        from quadkit.validation.rules import required

        v = ValidatorImpl().rule("name", required())
        assert v.is_valid({"name": "John"}) is True

    def test_is_valid_false(self) -> None:
        """Test is_valid returns False for invalid data."""
        from quadkit.validation.rules import required

        v = ValidatorImpl().rule("name", required())
        assert v.is_valid({}) is False


class TestAsyncValidator:
    """Tests for AsyncValidator."""

    def test_empty_async_validator(self) -> None:
        """Test creating empty async validator."""
        v = AsyncValidator()
        assert v._rules == {}

    def test_add_returns_self(self) -> None:
        """Test add() returns self for chaining."""
        v = AsyncValidator()
        result = v.add("name", Required())
        assert result is v

    @pytest.mark.asyncio
    async def test_async_validate_valid_data(self) -> None:
        """Test async validate passes with valid data."""
        v = AsyncValidator().add("name", Required())
        result = await v.validate({"name": "John"})
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_async_validate_invalid_data(self) -> None:
        """Test async validate fails with invalid data."""
        v = AsyncValidator().add("name", Required())
        result = await v.validate({"name": None})
        assert result.is_err()

    @pytest.mark.asyncio
    async def test_async_validate_missing_field(self) -> None:
        """Test async validate fails with missing field."""
        v = AsyncValidator().add("name", Required())
        result = await v.validate({})
        assert result.is_err()

    @pytest.mark.asyncio
    async def test_async_validate_multiple_errors(self) -> None:
        """Test async validate collects all errors."""
        from quadkit.validation.rules import email_format

        v = (
            AsyncValidator()
            .add("name", Required())
            .add("email", Required(), email_format())
        )
        result = await v.validate({"name": "", "email": "invalid"})
        assert result.is_err()
        errors = result.unwrap_err().errors
        assert len(errors) == 2

    @pytest.mark.asyncio
    async def test_async_validate_object_valid(self) -> None:
        """Test async validate_object with valid object."""
        v = AsyncValidator().add("name", Required())

        @dataclass
        class Person:
            name: str = "John"

        result = await v.validate_object(Person())
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_async_validate_object_invalid(self) -> None:
        """Test async validate_object with invalid object."""
        v = AsyncValidator().add("name", Required())

        @dataclass
        class Person:
            name: str | None = None

        result = await v.validate_object(Person())
        assert result.is_err()

    @pytest.mark.asyncio
    async def test_async_rule_integration(self) -> None:
        """Test async validator works with custom async rules."""

        class AsyncUppercase(AbstractAsyncRule):
            async def __call__(self, value: Any, field: str) -> Result[Any, FieldError]:
                if value is not None and value.upper() != value:
                    return Err(
                        FieldError(
                            field=field, message="Must be uppercase", code="uppercase"
                        )
                    )
                return Ok(value)

        v = AsyncValidator().add("name", Required(), AsyncUppercase())
        result = await v.validate({"name": "JOHN"})
        assert result.is_ok()

        result = await v.validate({"name": "John"})
        assert result.is_err()


class TestValidationConfigWiring:
    """stop_on_first_error / coerce_types (ValidationConfig fields)."""

    def test_stop_on_first_error_stops_after_first_field(self) -> None:
        """With stop_on_first_error, only the first failing field is reported."""
        v = (
            ValidatorImpl(stop_on_first_error=True)
            .rule(
                "a",
                Required(),
            )
            .rule("b", Required())
        )
        result = v.validate({})
        assert result.is_err()
        errors = result.unwrap_err().errors
        assert [e.field for e in errors] == ["a"]

    def test_default_collects_all_errors(self) -> None:
        """Default behaviour collects errors from every failing field."""
        v = ValidatorImpl().rule("a", Required()).rule("b", Required())
        result = v.validate({})
        assert result.is_err()
        errors = result.unwrap_err().errors
        assert {e.field for e in errors} == {"a", "b"}

    def test_coerce_types_coerces_object_attributes(self) -> None:
        """coerce_types=True coerces str values against the object's annotations."""

        @dataclass
        class Person:
            age: int
            name: str

        from quadkit.validation.rules import one_of

        v = ValidatorImpl(coerce_types=True).rule("age", one_of(42))
        person = Person(age="42", name="Ann")  # type: ignore[arg-type]
        result = v.validate_object(person)
        assert result.is_ok()  # "42" coerced to 42 via the annotation

    def test_coerce_types_default_off_leaves_values_untouched(self) -> None:
        """Without coerce_types, non-conforming values fail their rules."""
        from quadkit.validation.rules import one_of

        v = ValidatorImpl().rule("age", one_of(42))
        person = type("P", (), {"age": "42", "__annotations__": {"age": int}})()
        result = v.validate_object(person)
        assert result.is_err()  # "42" left as str -> not in {42}

    @pytest.mark.asyncio
    async def test_async_stop_on_first_error(self) -> None:
        """AsyncValidator honours stop_on_first_error too."""
        v = (
            AsyncValidator(stop_on_first_error=True)
            .rule(
                "a",
                Required(),
            )
            .rule("b", Required())
        )
        result = await v.validate({})
        assert result.is_err()
        assert [e.field for e in result.unwrap_err().errors] == ["a"]
