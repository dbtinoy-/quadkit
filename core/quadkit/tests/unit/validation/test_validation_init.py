"""Tests for validation/__init__ module."""
import pytest


class TestValidationLazyImports:
    """Tests for validation module lazy imports."""

    def test_lazy_import_field_error(self) -> None:
        """Test lazy import of FieldError."""
        from quadkit.validation import FieldError
        assert FieldError is not None

    def test_lazy_import_validate_input(self) -> None:
        """Test lazy import of validate_input."""
        from quadkit.validation import validate_input
        assert callable(validate_input)

    def test_lazy_import_field(self) -> None:
        """Test lazy import of Field."""
        from quadkit.validation import Field
        assert Field is not None

    def test_lazy_import_config_dict(self) -> None:
        """Test lazy import of ConfigDict."""
        from quadkit.validation import ConfigDict
        assert ConfigDict is not None

    def test_lazy_import_email_str(self) -> None:
        """Test lazy import of EmailStr."""
        from quadkit.validation import EmailStr
        assert EmailStr is not None

    def test_lazy_import_http_url(self) -> None:
        """Test lazy import of HttpUrl."""
        from quadkit.validation import HttpUrl
        assert HttpUrl is not None

    def test_lazy_import_secret_str(self) -> None:
        """Test lazy import of SecretStr."""
        from quadkit.validation import SecretStr
        assert SecretStr is not None

    def test_lazy_import_field_validator(self) -> None:
        """Test lazy import of field_validator."""
        from quadkit.validation import field_validator
        assert callable(field_validator)

    def test_lazy_import_model_validator(self) -> None:
        """Test lazy import of model_validator."""
        from quadkit.validation import model_validator
        assert callable(model_validator)

    def test_lazy_import_abstract_rule(self) -> None:
        """Test lazy import of AbstractRule."""
        from quadkit.validation import AbstractRule
        assert AbstractRule is not None

    def test_lazy_import_abstract_async_rule(self) -> None:
        """Test lazy import of AbstractAsyncRule."""
        from quadkit.validation import AbstractAsyncRule
        assert AbstractAsyncRule is not None

    def test_lazy_import_required(self) -> None:
        """Test lazy import of Required."""
        from quadkit.validation import Required
        assert Required is not None

    def test_lazy_import_min_length(self) -> None:
        """Test lazy import of MinLength."""
        from quadkit.validation import MinLength
        assert MinLength is not None

    def test_lazy_import_max_length(self) -> None:
        """Test lazy import of MaxLength."""
        from quadkit.validation import MaxLength
        assert MaxLength is not None

    def test_lazy_import_pattern(self) -> None:
        """Test lazy import of Pattern."""
        from quadkit.validation import Pattern
        assert Pattern is not None

    def test_lazy_import_range(self) -> None:
        """Test lazy import of Range."""
        from quadkit.validation import Range
        assert Range is not None

    def test_lazy_import_one_of(self) -> None:
        """Test lazy import of OneOf."""
        from quadkit.validation import OneOf
        assert OneOf is not None

    def test_lazy_import_email_format(self) -> None:
        """Test lazy import of EmailFormat."""
        from quadkit.validation import EmailFormat
        assert EmailFormat is not None

    def test_lazy_import_custom(self) -> None:
        """Test lazy import of Custom."""
        from quadkit.validation import Custom
        assert Custom is not None

    def test_lazy_import_required_func(self) -> None:
        """Test lazy import of required function."""
        from quadkit.validation import required
        assert callable(required)

    def test_lazy_import_min_length_func(self) -> None:
        """Test lazy import of min_length function."""
        from quadkit.validation import min_length
        assert callable(min_length)

    def test_lazy_import_max_length_func(self) -> None:
        """Test lazy import of max_length function."""
        from quadkit.validation import max_length
        assert callable(max_length)

    def test_lazy_import_pattern_func(self) -> None:
        """Test lazy import of pattern function."""
        from quadkit.validation import pattern
        assert callable(pattern)

    def test_lazy_import_range_check_func(self) -> None:
        """Test lazy import of range_check function."""
        from quadkit.validation import range_check
        assert callable(range_check)

    def test_lazy_import_one_of_func(self) -> None:
        """Test lazy import of one_of function."""
        from quadkit.validation import one_of
        assert callable(one_of)

    def test_lazy_import_email_format_func(self) -> None:
        """Test lazy import of email_format function."""
        from quadkit.validation import email_format
        assert callable(email_format)

    def test_lazy_import_custom_func(self) -> None:
        """Test lazy import of custom function."""
        from quadkit.validation import custom
        assert callable(custom)

    def test_lazy_import_validator(self) -> None:
        """Test lazy import of ValidatorImpl."""
        from quadkit.validation import ValidatorImpl
        assert ValidatorImpl is not None

    def test_lazy_import_async_validator(self) -> None:
        """Test lazy import of AsyncValidator."""
        from quadkit.validation import AsyncValidator
        assert AsyncValidator is not None

    def test_lazy_import_validation_config(self) -> None:
        """Test lazy import of ValidationConfig."""
        from quadkit.validation import ValidationConfig
        assert ValidationConfig is not None

    def test_lazy_import_validation_error(self) -> None:
        """Test lazy import of ValidationError."""
        from quadkit.validation import ValidationError
        assert ValidationError is not None


class TestValidationDir:
    """Tests for validation.__dir__()."""

    def test_dir_includes_lazy_imports(self) -> None:
        """Test __dir__ returns all lazy import keys."""
        from quadkit import validation
        d = dir(validation)
        assert "ValidatorImpl" in d
        assert "Required" in d

    def test_all_in_dir_are_in_all(self) -> None:
        """Test __all__ matches __dir__."""
        from quadkit import validation
        assert set(dir(validation)) == set(validation.__all__)


class TestValidationAttributeError:
    """Tests for validation module error handling."""

    def test_raises_attribute_error_for_unknown(self) -> None:
        """Test that unknown attributes raise AttributeError."""
        from quadkit import validation
        with pytest.raises(AttributeError, match="has no attribute"):
            validation.nonexistent_attribute