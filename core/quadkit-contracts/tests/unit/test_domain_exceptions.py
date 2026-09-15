"""Tests for contract domain exceptions."""

import pytest
from quadkit.contracts.exceptions.domain import (
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    AuthenticationError,
    AuthorizationError,
    RateLimitError,
    ConflictError,
    SerializationError,
    MappingError,
    WebError,
    FieldError,
    ValidationError,
)


class TestDomainError:
    def test_domain_error_code(self) -> None:
        exc = DomainError()
        assert exc.code == "QK_ERR_DOM_001"

    def test_domain_error_default_message(self) -> None:
        exc = DomainError()
        assert exc.message == "Domain error"


class TestNotFoundError:
    def test_not_found_error_code(self) -> None:
        exc = NotFoundError()
        assert exc.code == "QK_ERR_DOM_002"

    def test_not_found_error_default_message(self) -> None:
        exc = NotFoundError()
        assert exc.message == "Not found"


class TestPermissionDeniedError:
    def test_permission_denied_code(self) -> None:
        exc = PermissionDeniedError()
        assert exc.code == "QK_ERR_DOM_003"

    def test_permission_denied_default_message(self) -> None:
        exc = PermissionDeniedError()
        assert exc.message == "Permission denied"


class TestAuthenticationError:
    def test_authentication_error_code(self) -> None:
        exc = AuthenticationError()
        assert exc.code == "QK_ERR_DOM_004"

    def test_authentication_error_default_message(self) -> None:
        exc = AuthenticationError()
        assert exc.message == "Authentication failed"


class TestAuthorizationError:
    def test_authorization_error_code(self) -> None:
        exc = AuthorizationError()
        assert exc.code == "QK_ERR_DOM_005"

    def test_authorization_error_default_message(self) -> None:
        exc = AuthorizationError()
        assert exc.message == "Authorization failed"


class TestRateLimitError:
    def test_rate_limit_error_code(self) -> None:
        exc = RateLimitError()
        assert exc.code == "QK_ERR_DOM_006"

    def test_rate_limit_error_default_message(self) -> None:
        exc = RateLimitError()
        assert exc.message == "Rate limit exceeded"


class TestConflictError:
    def test_conflict_error_code(self) -> None:
        exc = ConflictError()
        assert exc.code == "QK_ERR_DOM_007"

    def test_conflict_error_default_message(self) -> None:
        exc = ConflictError()
        assert exc.message == "Conflict"


class TestSerializationError:
    def test_serialization_error_code(self) -> None:
        exc = SerializationError()
        assert exc.code == "QK_ERR_SERIAL_001"

    def test_serialization_error_default_message(self) -> None:
        exc = SerializationError()
        assert exc.message == "Serialization error"


class TestMappingError:
    def test_mapping_error_code(self) -> None:
        exc = MappingError()
        assert exc.code == "QK_ERR_MAP_001"

    def test_mapping_error_default_message(self) -> None:
        exc = MappingError()
        assert exc.message == "Mapping error"


class TestWebError:
    def test_web_error_code(self) -> None:
        exc = WebError()
        assert exc.code == "QK_ERR_WEB_001"

    def test_web_error_default_message(self) -> None:
        exc = WebError()
        assert exc.message == "Web error"


class TestFieldError:
    def test_field_error_creation(self) -> None:
        err = FieldError(field="email", message="Invalid email", code="invalid_email")
        assert err.field == "email"
        assert err.message == "Invalid email"
        assert err.code == "invalid_email"


class TestValidationError:
    def test_validation_error_code(self) -> None:
        exc = ValidationError()
        assert exc.code == "QK_ERR_VAL_002"

    def test_validation_error_default_message(self) -> None:
        exc = ValidationError()
        assert exc.message == "Validation failed"

    def test_validation_error_with_errors(self) -> None:
        err = FieldError(field="email", message="Invalid", code="invalid")
        exc = ValidationError(errors=[err])
        assert len(exc.errors) == 1
        assert exc.errors[0].field == "email"

    def test_validation_error_add_error(self) -> None:
        exc = ValidationError()
        exc.add_error("name", "Required", "required")
        assert len(exc.errors) == 1
        assert exc.errors[0].field == "name"
