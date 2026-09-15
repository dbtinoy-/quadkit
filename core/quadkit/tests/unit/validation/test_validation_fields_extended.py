"""Tests for validation/fields module - extended tests."""
import pytest

from quadkit.validation.schema import fields


class TestFieldValidatorDecoratorExtended:
    """Extended tests for field_validator decorator."""

    def test_decorator_sets_attributes(self) -> None:
        """Test decorator sets required attributes on function."""

        @fields.field_validator("name", "email")
        def validate(cls, value: str) -> str:
            return value

        assert hasattr(validate, "_field_validator")
        assert validate._field_validator is True

    def test_decorator_with_mode_before(self) -> None:
        """Test decorator with mode='before'."""

        @fields.field_validator("name", mode="before")
        def validate_before(cls, value: str) -> str:
            return value.strip()

        assert validate_before._validator_mode == "before"
        assert validate_before._validator_fields == ("name",)

    def test_decorator_with_mode_after(self) -> None:
        """Test decorator with mode='after'."""

        @fields.field_validator("value", mode="after")
        def validate_after(cls, value: str) -> str:
            return value

        assert validate_after._validator_mode == "after"

    def test_decorator_preserves_function(self) -> None:
        """Test decorator preserves function behavior."""

        @fields.field_validator("name")
        def validate_name(cls, value: str) -> str:
            return value.upper() if value else ""

        result = validate_name(None, "test")
        assert result == "TEST"

    def test_decorator_with_classmethod(self) -> None:
        """Test decorator works with classmethod."""

        class MyClass:
            @classmethod
            @fields.field_validator("field")
            def validate_field(cls, value: str) -> str:
                return value

        # Should have the attributes
        assert hasattr(MyClass.validate_field, "_field_validator")


class TestModelValidatorDecoratorExtended:
    """Extended tests for model_validator decorator."""

    def test_decorator_sets_attributes(self) -> None:
        """Test decorator sets required attributes."""

        def validate_model(values: dict) -> dict:
            return values

        decorated = fields.model_validator()(validate_model)
        assert hasattr(decorated, "_model_validator")
        assert decorated._model_validator is True

    def test_decorator_mode_wrap(self) -> None:
        """Test decorator with mode='wrap'."""

        def validate_wrap(values: dict) -> dict:
            return values

        decorated = fields.model_validator(mode="wrap")(validate_wrap)
        assert decorated._validator_mode == "wrap"

    def test_decorator_mode_before(self) -> None:
        """Test decorator with mode='before'."""

        def validate_before(values: dict) -> dict:
            return values

        decorated = fields.model_validator(mode="before")(validate_before)
        assert decorated._validator_mode == "before"

    def test_decorator_mode_after(self) -> None:
        """Test decorator with mode='after'."""

        def validate_after(values: dict) -> dict:
            return values

        decorated = fields.model_validator(mode="after")(validate_after)
        assert decorated._validator_mode == "after"


class TestFieldReExportsExtended:
    """Extended tests for re-exported types."""

    def test_field_can_be_used_as_field(self) -> None:
        """Test Field can be used for field definition."""
        from dataclasses import dataclass

        @dataclass
        class Person:
            name: str = fields.Field(description="Person's name")

        p = Person(name="John")
        assert p.name == "John"

    def test_config_dict_is_dict(self) -> None:
        """Test ConfigDict is a dict-like."""
        config = fields.ConfigDict(extra="forbid")
        assert config.get("extra") == "forbid"

    def test_email_str_type_exists(self) -> None:
        """Test EmailStr type is available."""
        # Just check it exists and is a type
        assert hasattr(fields, "EmailStr")

    def test_http_url_type_exists(self) -> None:
        """Test HttpUrl type is available."""
        assert hasattr(fields, "HttpUrl")

    def test_secret_str_type_exists(self) -> None:
        """Test SecretStr type is available."""
        assert hasattr(fields, "SecretStr")


class TestDecoratorWithKwargs:
    """Test that decorators accept and ignore extra kwargs."""

    def test_field_validator_ignores_extra_kwargs(self) -> None:
        """Test field_validator ignores extra kwargs."""

        @fields.field_validator("name", some_extra="ignored", another=123)
        def validate(cls, value: str) -> str:
            return value

        assert hasattr(validate, "_field_validator")

    def test_model_validator_ignores_extra_kwargs(self) -> None:
        """Test model_validator ignores extra kwargs."""

        @fields.model_validator(extra_arg="ignored")
        def validate(values: dict) -> dict:
            return values

        assert hasattr(validate, "_model_validator")