"""Tests for domain exceptions from contracts."""

from quadkit.contracts.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    FieldError,
    QuadkitError,
    MappingError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    SerializationError,
    ValidationError,
    WebError,
)


class TestDomainExceptionHierarchy:
    """Tests for domain exception inheritance."""

    def test_domain_error_inherits_from_quadkit(self) -> None:
        """DomainError inherits from QuadkitError."""
        assert issubclass(DomainError, QuadkitError)

    def test_all_domain_errors_inherit(self) -> None:
        """All domain exceptions inherit from DomainError."""
        assert issubclass(NotFoundError, DomainError)
        assert issubclass(PermissionDeniedError, DomainError)
        assert issubclass(AuthenticationError, DomainError)
        assert issubclass(AuthorizationError, DomainError)
        assert issubclass(RateLimitError, DomainError)
        assert issubclass(ConflictError, DomainError)
        assert issubclass(WebError, DomainError)
        assert issubclass(ValidationError, DomainError)


class TestDomainErrorCodes:
    """Tests for domain exception error codes."""

    def test_domain_error_has_code(self) -> None:
        """DomainError has _code attribute."""
        exc = DomainError()
        assert exc._code == "QK_ERR_DOM_001"

    def test_not_found_error_has_code(self) -> None:
        """NotFoundError has _code."""
        exc = NotFoundError()
        assert exc._code == "QK_ERR_DOM_002"

    def test_permission_denied_error_has_code(self) -> None:
        """PermissionDeniedError has _code."""
        exc = PermissionDeniedError()
        assert exc._code == "QK_ERR_DOM_003"

    def test_authentication_error_has_code(self) -> None:
        """AuthenticationError has _code."""
        exc = AuthenticationError()
        assert exc._code == "QK_ERR_DOM_004"

    def test_authorization_error_has_code(self) -> None:
        """AuthorizationError has _code."""
        exc = AuthorizationError()
        assert exc._code == "QK_ERR_DOM_005"

    def test_rate_limit_error_has_code(self) -> None:
        """RateLimitError has _code."""
        exc = RateLimitError()
        assert exc._code == "QK_ERR_DOM_006"

    def test_conflict_error_has_code(self) -> None:
        """ConflictError has _code."""
        exc = ConflictError()
        assert exc._code == "QK_ERR_DOM_007"


class TestSerializationError:
    """Tests for SerializationError."""

    def test_inherits_from_quadkit_error(self) -> None:
        """SerializationError inherits from QuadkitError."""
        assert issubclass(SerializationError, QuadkitError)

    def test_has_code(self) -> None:
        """SerializationError has _code."""
        exc = SerializationError()
        assert exc._code == "QK_ERR_SERIAL_001"


class TestMappingError:
    """Tests for MappingError."""

    def test_inherits_from_quadkit_error(self) -> None:
        """MappingError inherits from QuadkitError."""
        assert issubclass(MappingError, QuadkitError)

    def test_has_code(self) -> None:
        """MappingError has _code."""
        exc = MappingError()
        assert exc._code == "QK_ERR_MAP_001"


class TestFieldError:
    """Tests for FieldError dataclass."""

    def test_creates_with_all_fields(self) -> None:
        """FieldError can be created with field, message, code."""
        error = FieldError(field="email", message="Invalid format", code="format")
        assert error.field == "email"
        assert error.message == "Invalid format"
        assert error.code == "format"

    def test_requires_all_fields(self) -> None:
        """FieldError requires all fields to be specified."""
        error = FieldError(field="name", message="Required", code="required")
        assert error.field == "name"
        assert error.message == "Required"
        assert error.code == "required"


class TestValidationError:
    """Tests for ValidationError."""

    def test_inherits_from_domain_error(self) -> None:
        """ValidationError inherits from DomainError."""
        assert issubclass(ValidationError, DomainError)

    def test_has_code(self) -> None:
        """ValidationError has _code."""
        exc = ValidationError()
        assert exc._code == "QK_ERR_VAL_002"

    def test_stores_field_errors(self) -> None:
        """ValidationError stores field errors."""
        errors = [
            FieldError(field="email", message="Invalid", code="format"),
            FieldError(field="name", message="Required", code="required"),
        ]
        exc = ValidationError(errors=errors)
        assert len(exc.errors) == 2
        assert exc.errors[0].field == "email"
        assert exc.errors[1].field == "name"

    def test_add_error_method(self) -> None:
        """ValidationError.add_error() adds field errors."""
        exc = ValidationError()
        exc.add_error("email", "Invalid format", "format")

        assert len(exc.errors) == 1
        assert exc.errors[0].field == "email"
        assert exc.errors[0].message == "Invalid format"

    def test_add_error_returns_self(self) -> None:
        """ValidationError.add_error() returns self for chaining."""
        exc = ValidationError()
        result = exc.add_error("field", "message")

        assert result is exc

    def test_add_multiple_errors(self) -> None:
        """Can add multiple errors via chaining."""
        exc = ValidationError()
        exc.add_error("email", "Invalid", "format").add_error(
            "name", "Required", "required"
        )

        assert len(exc.errors) == 2
