"""Unit tests for validation exceptions."""

import pytest

from quadkit.validation.exceptions import (
    FieldError,
    ValidationError,
    ValidationSystemError,
)


class TestValidationError:
    def test_inheritance(self) -> None:
        assert issubclass(ValidationError, Exception)


class TestFieldError:
    def test_inheritance(self) -> None:
        assert issubclass(FieldError, Exception)


class TestValidationSystemError:
    def test_inheritance(self) -> None:
        assert issubclass(ValidationSystemError, Exception)

    def test_code(self) -> None:
        assert ValidationSystemError._code == "QK_ERR_VAL_004"

    def test_default_message(self) -> None:
        exc = ValidationSystemError()
        assert "Validation system error" in str(exc)