"""Tests for the validation module — rules, validator, and decorator."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.validation.decorators import validate_input
from quadkit.validation.rules import (
    Custom,
    EmailFormat,
    MaxLength,
    MinLength,
    OneOf,
    Pattern,
    Range,
    Required,
    AbstractRule,
    custom,
    email_format,
    max_length,
    min_length,
    one_of,
    pattern,
    range_check,
    required,
)
from quadkit.validation.engine import ValidatorImpl

# ---------------------------------------------------------------------------
# Rule: Required
# ---------------------------------------------------------------------------


class TestRequired:
    """Tests for the Required validation rule."""

    def test_none_value_fails(self) -> None:
        result = Required()(None, "name")
        assert result.is_err()
        err = result.unwrap_err()
        assert err.code == "required"
        assert err.field == "name"

    def test_empty_string_fails(self) -> None:
        result = Required()("", "email")
        assert result.is_err()

    def test_blank_string_fails(self) -> None:
        result = Required()("   ", "email")
        assert result.is_err()

    def test_valid_value_passes(self) -> None:
        result = Required()("alice", "name")
        assert result.is_ok()
        assert result.unwrap() == "alice"

    def test_zero_passes(self) -> None:
        """Zero is a valid (non-None) value."""
        result = Required()(0, "count")
        assert result.is_ok()


# ---------------------------------------------------------------------------
# Rule: MinLength
# ---------------------------------------------------------------------------


class TestMinLength:
    """Tests for the MinLength validation rule."""

    def test_too_short_fails(self) -> None:
        result = MinLength(3)("ab", "name")
        assert result.is_err()
        assert result.unwrap_err().code == "min_length"

    def test_exact_length_passes(self) -> None:
        result = MinLength(3)("abc", "name")
        assert result.is_ok()

    def test_longer_passes(self) -> None:
        result = MinLength(2)("hello", "name")
        assert result.is_ok()

    def test_none_skipped(self) -> None:
        """None values are skipped (not validated for length)."""
        result = MinLength(5)(None, "name")
        assert result.is_ok()


# ---------------------------------------------------------------------------
# Rule: MaxLength
# ---------------------------------------------------------------------------


class TestMaxLength:
    """Tests for the MaxLength validation rule."""

    def test_too_long_fails(self) -> None:
        result = MaxLength(3)("abcd", "name")
        assert result.is_err()
        assert result.unwrap_err().code == "max_length"

    def test_exact_length_passes(self) -> None:
        result = MaxLength(3)("abc", "name")
        assert result.is_ok()

    def test_shorter_passes(self) -> None:
        result = MaxLength(10)("hi", "name")
        assert result.is_ok()

    def test_none_skipped(self) -> None:
        result = MaxLength(5)(None, "name")
        assert result.is_ok()


# ---------------------------------------------------------------------------
# Rule: Pattern
# ---------------------------------------------------------------------------


class TestPattern:
    """Tests for the Pattern validation rule."""

    def test_matching_passes(self) -> None:
        result = Pattern(r"^\d{3}$")("123", "code")
        assert result.is_ok()

    def test_non_matching_fails(self) -> None:
        result = Pattern(r"^\d{3}$")("12", "code")
        assert result.is_err()
        assert result.unwrap_err().code == "pattern"

    def test_none_skipped(self) -> None:
        result = Pattern(r"^\d+$")(None, "code")
        assert result.is_ok()


# ---------------------------------------------------------------------------
# Rule: Range
# ---------------------------------------------------------------------------


class TestRange:
    """Tests for the Range validation rule."""

    def test_below_min_fails(self) -> None:
        result = Range(min_val=10)(5, "age")
        assert result.is_err()
        assert result.unwrap_err().code == "range_min"

    def test_above_max_fails(self) -> None:
        result = Range(max_val=100)(200, "age")
        assert result.is_err()
        assert result.unwrap_err().code == "range_max"

    def test_within_range_passes(self) -> None:
        result = Range(min_val=1, max_val=100)(50, "age")
        assert result.is_ok()

    def test_boundary_values_pass(self) -> None:
        assert Range(min_val=1, max_val=10)(1, "v").is_ok()
        assert Range(min_val=1, max_val=10)(10, "v").is_ok()

    def test_none_skipped(self) -> None:
        result = Range(min_val=0)(None, "age")
        assert result.is_ok()

    def test_no_bounds_passes(self) -> None:
        result = Range()(999, "x")
        assert result.is_ok()


# ---------------------------------------------------------------------------
# Rule: OneOf
# ---------------------------------------------------------------------------


class TestOneOf:
    """Tests for the OneOf validation rule."""

    def test_valid_choice_passes(self) -> None:
        result = OneOf("a", "b", "c")("b", "status")
        assert result.is_ok()

    def test_invalid_choice_fails(self) -> None:
        result = OneOf("a", "b")("x", "status")
        assert result.is_err()
        assert result.unwrap_err().code == "one_of"

    def test_none_skipped(self) -> None:
        result = OneOf("a", "b")(None, "status")
        assert result.is_ok()


# ---------------------------------------------------------------------------
# Rule: EmailFormat
# ---------------------------------------------------------------------------


class TestEmailFormat:
    """Tests for the EmailFormat validation rule."""

    def test_valid_email_passes(self) -> None:
        assert EmailFormat()("user@example.com", "email").is_ok()

    def test_invalid_email_fails(self) -> None:
        result = EmailFormat()("not-an-email", "email")
        assert result.is_err()
        assert result.unwrap_err().code == "email_format"

    def test_missing_domain_fails(self) -> None:
        assert EmailFormat()("user@", "email").is_err()

    def test_none_skipped(self) -> None:
        assert EmailFormat()(None, "email").is_ok()


# ---------------------------------------------------------------------------
# Rule: Custom
# ---------------------------------------------------------------------------


class TestCustom:
    """Tests for the Custom validation rule."""

    def test_predicate_true_passes(self) -> None:
        result = Custom(lambda v: v > 0, "must be positive")(5, "amount")
        assert result.is_ok()

    def test_predicate_false_fails(self) -> None:
        result = Custom(lambda v: v > 0, "must be positive")(-1, "amount")
        assert result.is_err()
        err = result.unwrap_err()
        assert err.code == "custom"
        assert err.message == "must be positive"

    def test_none_skipped(self) -> None:
        result = Custom(lambda v: v > 0, "must be positive")(None, "amount")
        assert result.is_ok()


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


class TestFactoryFunctions:
    """Test convenience factory functions return correct rule types."""

    def test_required_factory(self) -> None:
        assert isinstance(required(), Required)

    def test_min_length_factory(self) -> None:
        assert isinstance(min_length(3), MinLength)

    def test_max_length_factory(self) -> None:
        assert isinstance(max_length(10), MaxLength)

    def test_pattern_factory(self) -> None:
        assert isinstance(pattern(r"\d+"), Pattern)

    def test_range_check_factory(self) -> None:
        assert isinstance(range_check(min_val=0), Range)

    def test_one_of_factory(self) -> None:
        assert isinstance(one_of("a", "b"), OneOf)

    def test_email_format_factory(self) -> None:
        assert isinstance(email_format(), EmailFormat)

    def test_custom_factory(self) -> None:
        assert isinstance(custom(lambda v: True, "ok"), Custom)

    def test_all_are_rule_subclasses(self) -> None:
        for r in [required(), min_length(1), max_length(1), pattern(r"."),
                   range_check(), one_of("a"), email_format(),
                   custom(lambda v: True, "ok")]:
            assert isinstance(r, AbstractRule)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class TestValidator:
    """Tests for the ValidatorImpl composable validation."""

    def test_valid_data_returns_ok(self) -> None:
        v = ValidatorImpl().rule("name", required(), min_length(2))
        result = v.validate({"name": "Alice"})
        assert result.is_ok()
        assert result.unwrap() == {"name": "Alice"}

    def test_invalid_data_returns_err(self) -> None:
        v = ValidatorImpl().rule("name", required())
        result = v.validate({"name": ""})
        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, ValidationError)

    def test_multiple_fields_all_errors_collected(self) -> None:
        """All fields are validated; errors from every failing field collected."""
        v = (
            ValidatorImpl()
            .rule("name", required())
            .rule("email", required(), email_format())
        )
        result = v.validate({"name": "", "email": ""})
        assert result.is_err()
        errors = result.unwrap_err().errors
        fields = {e.field for e in errors}
        assert "name" in fields
        assert "email" in fields

    def test_stops_on_first_error_per_field(self) -> None:
        """For a single field, stops at the first failing rule."""
        v = ValidatorImpl().rule("name", required(), min_length(5))
        result = v.validate({"name": ""})
        assert result.is_err()
        errors = result.unwrap_err().errors
        # Should only have 1 error for "name" (required), not 2
        assert len([e for e in errors if e.field == "name"]) == 1

    def test_chaining_returns_self(self) -> None:
        v = ValidatorImpl()
        result = v.rule("a", required()).rule("b", required())
        assert result is v

    def test_is_valid_shorthand(self) -> None:
        v = ValidatorImpl().rule("name", required())
        assert v.is_valid({"name": "ok"}) is True
        assert v.is_valid({"name": ""}) is False

    def test_missing_field_defaults_to_none(self) -> None:
        v = ValidatorImpl().rule("age", required())
        result = v.validate({})
        assert result.is_err()

    def test_validate_object(self) -> None:
        """validate_object extracts attributes via getattr."""

        @dataclass
        class User:
            name: str
            email: str

        v = ValidatorImpl().rule("name", required()).rule("email", email_format())
        user = User(name="Alice", email="alice@example.com")
        result = v.validate_object(user)
        assert result.is_ok()
        assert result.unwrap() is user

    def test_validate_object_fails(self) -> None:
        @dataclass
        class User:
            name: str
            email: str

        v = ValidatorImpl().rule("email", email_format())
        user = User(name="Alice", email="not-valid")
        result = v.validate_object(user)
        assert result.is_err()


# ---------------------------------------------------------------------------
# @validate_input decorator
# ---------------------------------------------------------------------------


class TestValidateInputDecorator:
    """Tests for the @validate_input decorator."""

    @pytest.mark.asyncio
    async def test_async_function_passes(self) -> None:
        v = ValidatorImpl().rule("name", required())

        @validate_input(v)
        async def create_user(name: str) -> str:
            return f"created:{name}"

        result = await create_user(name="Alice")
        assert result == "created:Alice"

    @pytest.mark.asyncio
    async def test_async_function_fails(self) -> None:
        v = ValidatorImpl().rule("name", required())

        @validate_input(v)
        async def create_user(name: str) -> str:
            return f"created:{name}"

        with pytest.raises(ValidationError):
            await create_user(name="")

    def test_sync_function_passes(self) -> None:
        v = ValidatorImpl().rule("name", required())

        @validate_input(v)
        def create_user(name: str) -> str:
            return f"created:{name}"

        result = create_user(name="Alice")
        assert result == "created:Alice"

    def test_sync_function_fails(self) -> None:
        v = ValidatorImpl().rule("name", required())

        @validate_input(v)
        def create_user(name: str) -> str:
            return f"created:{name}"

        with pytest.raises(ValidationError):
            create_user(name="")

    @pytest.mark.asyncio
    async def test_dict_as_first_arg(self) -> None:
        """When first arg is a dict, it is validated directly."""
        v = ValidatorImpl().rule("name", required())

        @validate_input(v)
        async def process(data: dict) -> str:
            return data["name"]

        result = await process({"name": "Bob"})
        assert result == "Bob"

    @pytest.mark.asyncio
    async def test_positional_args_mapped(self) -> None:
        """Positional args are mapped to parameter names."""
        v = ValidatorImpl().rule("name", required())

        @validate_input(v)
        async def greet(name: str) -> str:
            return f"hi {name}"

        result = await greet("World")
        assert result == "hi World"
