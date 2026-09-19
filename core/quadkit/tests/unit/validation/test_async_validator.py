"""Tests for validation/validator.py - AsyncValidator."""

import pytest

from quadkit.contracts.exceptions.domain import FieldError, ValidationError
from quadkit.result import Err, Ok
from quadkit.validation.rules import AbstractAsyncRule, AbstractRule, Required
from quadkit.validation.engine import AsyncValidator


class TestAsyncValidatorInit:
    """Tests for AsyncValidator initialization."""

    def test_init_creates_empty_rules(self) -> None:
        """Test that AsyncValidator initializes with empty rules."""
        validator = AsyncValidator()
        assert validator._rules == {}

    def test_init_allows_type_parameter(self) -> None:
        """Test that AsyncValidator accepts type parameter."""
        validator: AsyncValidator[dict] = AsyncValidator()
        assert validator is not None


class TestAsyncValidatorAdd:
    """Tests for AsyncValidator.add method."""

    def test_add_single_rule(self) -> None:
        """Test adding a single rule."""
        validator = AsyncValidator()
        result = validator.add("name", Required())
        assert result is validator

    def test_add_multiple_rules(self) -> None:
        """Test adding multiple rules at once."""
        validator = AsyncValidator()
        validator.add("name", Required())
        assert "name" in validator._rules
        assert len(validator._rules["name"]) == 1


class TestAsyncValidatorValidate:
    """Tests for AsyncValidator.validate method."""

    @pytest.mark.asyncio
    async def test_validate_with_sync_rules(self) -> None:
        """Test validation with sync rules returns Ok."""
        validator = AsyncValidator()
        validator.add("name", Required())

        result = await validator.validate({"name": "Alice"})
        assert result.is_ok()
        assert result.unwrap() == {"name": "Alice"}

    @pytest.mark.asyncio
    async def test_validate_with_sync_rules_fails(self) -> None:
        """Test validation with sync rules returns Err on failure."""
        validator = AsyncValidator()
        validator.add("name", Required())

        result = await validator.validate({"name": ""})
        assert result.is_err()
        err = result.unwrap_err()
        assert isinstance(err, ValidationError)

    @pytest.mark.asyncio
    async def test_validate_with_async_rules(self) -> None:
        """Test validation with async rules."""

        class AsyncRequired(AbstractAsyncRule[str]):
            async def __call__(self, value: str, field_name: str) -> Err | Ok:
                if value is None or value == "":
                    return Err(FieldError(field=field_name, message="required", code="required"))
                return Ok(value)

        validator = AsyncValidator()
        validator.add("name", AsyncRequired())

        result = await validator.validate({"name": "Alice"})
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_validate_with_async_rules_fails(self) -> None:
        """Test validation with async rules fails correctly."""

        class AsyncRequired(AbstractAsyncRule[str]):
            async def __call__(self, value: str, field_name: str) -> Err | Ok:
                if value is None or value == "":
                    return Err(FieldError(field=field_name, message="required", code="required"))
                return Ok(value)

        validator = AsyncValidator()
        validator.add("name", AsyncRequired())

        result = await validator.validate({"name": ""})
        assert result.is_err()

    @pytest.mark.asyncio
    async def test_validate_mixed_sync_and_async_rules(self) -> None:
        """Test validation with both sync and async rules."""

        class AsyncUppercase(AbstractAsyncRule[str]):
            async def __call__(self, value: str, field_name: str) -> Err | Ok:
                if value and not value.isupper():
                    return Err(FieldError(field=field_name, message="must be uppercase", code="uppercase"))
                return Ok(value)

        validator = AsyncValidator()
        validator.add("code", Required(), AsyncUppercase())

        result = await validator.validate({"code": "ABC"})
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_validate_multiple_fields(self) -> None:
        """Test validation of multiple fields."""
        validator = AsyncValidator()
        validator.add("name", Required())
        validator.add("email", Required())

        result = await validator.validate({"name": "Alice", "email": "alice@example.com"})
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_validate_stops_on_first_error_per_field(self) -> None:
        """Test that validation stops at first error per field."""
        validator = AsyncValidator()
        validator.add("name", Required())

        result = await validator.validate({"name": ""})
        assert result.is_err()
        errors = result.unwrap_err().errors
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_validate_missing_field(self) -> None:
        """Test validation with missing field."""
        validator = AsyncValidator()
        validator.add("name", Required())

        result = await validator.validate({})
        assert result.is_err()


class TestAsyncValidatorValidateObject:
    """Tests for AsyncValidator.validate_object method."""

    @pytest.mark.asyncio
    async def test_validate_object_success(self) -> None:
        """Test validate_object returns Ok on success."""
        from dataclasses import dataclass

        @dataclass
        class User:
            name: str = ""

        validator = AsyncValidator()
        validator.add("name", Required())

        user = User(name="Alice")
        result = await validator.validate_object(user)
        assert result.is_ok()
        assert result.unwrap() is user

    @pytest.mark.asyncio
    async def test_validate_object_failure(self) -> None:
        """Test validate_object returns Err on failure."""
        from dataclasses import dataclass

        @dataclass
        class User:
            name: str = ""

        validator = AsyncValidator()
        validator.add("name", Required())

        user = User(name="")
        result = await validator.validate_object(user)
        assert result.is_err()

    @pytest.mark.asyncio
    async def test_validate_object_with_async_rules(self) -> None:
        """Test validate_object with async rules."""
        from dataclasses import dataclass

        @dataclass
        class User:
            name: str = ""

        class AsyncUppercase(AbstractAsyncRule[str]):
            async def __call__(self, value: str, field_name: str) -> Err | Ok:
                if value and not value.isupper():
                    return Err(FieldError(field=field_name, message="must be uppercase", code="uppercase"))
                return Ok(value)

        validator = AsyncValidator()
        validator.add("name", AsyncUppercase())

        user = User(name="ALICE")
        result = await validator.validate_object(user)
        assert result.is_ok()


class TestAsyncValidatorChaining:
    """Tests for AsyncValidator method chaining."""

    @pytest.mark.asyncio
    async def test_add_returns_self_for_chaining(self) -> None:
        """Test that add() returns self for method chaining."""
        validator = AsyncValidator()
        result = validator.add("a", Required()).add("b", Required())
        assert result is validator

    @pytest.mark.asyncio
    async def test_fluent_interface(self) -> None:
        """Test fluent interface for building validators."""
        validator = (
            AsyncValidator()
            .add("name", Required())
            .add("email", Required())
        )
        result = await validator.validate({"name": "Alice", "email": "a@b.com"})
        assert result.is_ok()
