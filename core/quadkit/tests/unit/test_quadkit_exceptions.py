"""Tests for Quadkit exception hierarchy."""

import pytest

from quadkit.contracts.exceptions.base import QuadkitError
from quadkit.contracts.exceptions.provider import ModuleError
from quadkit.exceptions import (
    ConfigurationError,
    DomainModelError,
    InjectionError,
    QuadkitException,
    SerializationError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""

    def test_quadkit_exception_extends_quadkit_error(self) -> None:
        """QuadkitException must extend QuadkitError from contracts."""
        assert issubclass(QuadkitException, QuadkitError)

    def test_quadkit_exception_is_base(self) -> None:
        """QuadkitException is the base for all framework exceptions."""
        assert issubclass(ConfigurationError, QuadkitException)
        assert issubclass(InjectionError, QuadkitException)
        assert issubclass(ValidationError, QuadkitException)
        assert issubclass(SerializationError, QuadkitException)
        assert issubclass(DomainModelError, QuadkitException)
        # ModuleError is from contracts and inherits QuadkitError, not QuadkitException
        assert issubclass(ModuleError, QuadkitError)

    def test_all_exceptions_inherit_from_exception(self) -> None:
        """All Quadkit exceptions inherit from Exception."""
        assert issubclass(QuadkitException, Exception)
        assert issubclass(ConfigurationError, Exception)
        assert issubclass(InjectionError, Exception)
        assert issubclass(ValidationError, Exception)
        assert issubclass(SerializationError, Exception)
        assert issubclass(DomainModelError, Exception)
        assert issubclass(ModuleError, Exception)  # via QuadkitError → Exception

    def test_all_exceptions_inherit_from_quadkit_error(self) -> None:
        """All domain exceptions inherit from QuadkitError."""
        assert issubclass(QuadkitException, QuadkitError)
        assert issubclass(ConfigurationError, QuadkitError)
        assert issubclass(InjectionError, QuadkitError)


class TestExceptionMessages:
    """Tests for exception messages and instantiation."""

    def test_quadkit_exception_with_message(self) -> None:
        """QuadkitException can be instantiated with a message."""
        msg = "Something went wrong"
        exc = QuadkitException(msg)
        # QuadkitError.__str__ includes the code prefix, but the message is present
        assert msg in str(exc)

    def test_quadkit_exception_message_attribute(self) -> None:
        """QuadkitException stores message on .message attribute."""
        msg = "Something went wrong"
        exc = QuadkitException(msg)
        assert exc.message == msg

    def test_configuration_error_with_context(self) -> None:
        """ConfigurationError includes context in message."""
        exc = ConfigurationError("Invalid setting: debug")
        assert "Invalid setting" in str(exc)

    def test_injection_error_with_service_name(self) -> None:
        """InjectionError includes service information."""
        exc = InjectionError("Cannot resolve: UserService")
        assert "UserService" in str(exc)

    def test_validation_error_with_message(self) -> None:
        """ValidationError includes message in string representation."""
        exc = ValidationError("email: Invalid email format")
        assert "email" in str(exc)
        assert "Invalid" in str(exc)


class TestExceptionChaining:
    """Tests for exception chaining."""

    def test_exception_with_cause(self) -> None:
        """Exceptions can chain from other exceptions."""
        original = ValueError("original error")
        exc = QuadkitException("wrapped")
        exc.__cause__ = original
        assert exc.__cause__ is original

    def test_injection_error_chains_resolution_error(self) -> None:
        """InjectionError can chain from underlying errors."""
        original = RuntimeError("container error")
        exc = InjectionError("resolution failed")
        exc.__cause__ = original
        assert exc.__cause__ is original


class TestExceptionCatching:
    """Tests for exception catching patterns."""

    def test_catch_all_quadkit_exceptions(self) -> None:
        """Can catch all Quadkit exceptions with base class."""
        framework_errors = [
            ConfigurationError("config"),
            InjectionError("inject"),
            ValidationError("validation failed"),
            SerializationError("json"),
            DomainModelError("domain"),
        ]
        for error in framework_errors:
            assert isinstance(error, QuadkitException)

        # ModuleError is from contracts — catches as QuadkitError, not QuadkitException
        assert isinstance(ModuleError("module"), QuadkitError)

    def test_catch_all_as_quadkit_error(self) -> None:
        """Can catch all Quadkit exceptions as QuadkitError."""
        errors = [
            ConfigurationError("config"),
            InjectionError("inject"),
            ValidationError("validation failed"),
        ]
        for error in errors:
            assert isinstance(error, QuadkitError)

    def test_catch_specific_exception(self) -> None:
        """Can catch specific exception types."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("specific error")

    def test_catch_by_parent_exception(self) -> None:
        """Specific exceptions can be caught by parent type."""
        with pytest.raises(QuadkitException):
            raise ValidationError("validation failed")
