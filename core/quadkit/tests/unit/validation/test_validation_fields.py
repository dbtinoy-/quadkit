"""Tests for validation/fields module."""
import pytest

from quadkit.validation.schema import fields


class TestFieldValidatorDecorator:
    """Tests for field_validator decorator."""

    def test_field_validator_basic(self) -> None:
        """Test basic field_validator decorator."""

        @fields.field_validator("name")
        def validate_name(cls, value: str) -> str:
            return value

        assert hasattr(validate_name, "_field_validator")
        assert validate_name._field_validator is True
        assert validate_name._validator_mode == "after"
        assert validate_name._validator_fields == ("name",)

    def test_field_validator_multiple_fields(self) -> None:
        """Test field_validator with multiple fields."""

        @fields.field_validator("name", "email")
        def validate_fields(cls, value: str) -> str:
            return value

        assert validate_fields._validator_fields == ("name", "email")

    def test_field_validator_before_mode(self) -> None:
        """Test field_validator with before mode."""

        @fields.field_validator("name", mode="before")
        def validate_before(cls, value: str) -> str:
            return value

        assert validate_before._validator_mode == "before"

    def test_field_validator_classmethod(self) -> None:
        """Test field_validator with classmethod."""

        class MyClass:
            @classmethod
            @fields.field_validator("name")
            def validate_name(cls, value: str) -> str:
                return value

        assert hasattr(MyClass.validate_name, "_field_validator")


class TestModelValidatorDecorator:
    """Tests for model_validator decorator."""

    def test_model_validator_basic(self) -> None:
        """Test basic model_validator decorator."""

        def validate_model(values: dict) -> dict:
            return values

        decorated = fields.model_validator()(validate_model)
        assert hasattr(decorated, "_model_validator")
        assert decorated._model_validator is True
        assert decorated._validator_mode == "wrap"

    def test_model_validator_before_mode(self) -> None:
        """Test model_validator with before mode."""

        def validate_before(values: dict) -> dict:
            return values

        decorated = fields.model_validator(mode="before")(validate_before)
        assert decorated._validator_mode == "before"

    def test_model_validator_after_mode(self) -> None:
        """Test model_validator with after mode."""

        def validate_after(values: dict) -> dict:
            return values

        decorated = fields.model_validator(mode="after")(validate_after)
        assert decorated._validator_mode == "after"


class TestFieldReExports:
    """Tests that fields module re-exports are available."""

    def test_config_dict_available(self) -> None:
        """Test ConfigDict is available."""
        assert fields.ConfigDict is not None

    def test_email_str_available(self) -> None:
        """Test EmailStr is available."""
        assert fields.EmailStr is not None

    def test_field_available(self) -> None:
        """Test Field is available."""
        assert fields.Field is not None

    def test_http_url_available(self) -> None:
        """Test HttpUrl is available."""
        assert fields.HttpUrl is not None

    def test_secret_str_available(self) -> None:
        """Test SecretStr is available."""
        assert fields.SecretStr is not None


class TestFieldValidatorKwargIgnore:
    """Test that field_validator accepts but ignores kwargs."""

    def test_accepts_kwargs(self) -> None:
        """Test that extra kwargs are accepted."""

        @fields.field_validator("name", extra_arg="ignored", another=123)
        def validate_name(cls, value: str) -> str:
            return value

        assert hasattr(validate_name, "_field_validator")


class TestModelValidatorKwargIgnore:
    """Test that model_validator accepts but ignores kwargs."""

    def test_accepts_kwargs(self) -> None:
        """Test that extra kwargs are accepted."""

        @fields.model_validator(extra_arg="ignored", another=123)
        def validate_model(values: dict) -> dict:
            return values

        assert hasattr(validate_model, "_model_validator")