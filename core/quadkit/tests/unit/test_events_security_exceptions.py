"""Tests for events and security exceptions from contracts."""

from quadkit.contracts.exceptions import (
    CORSViolationError,
    DuplicateHandlerError,
    EventError,
    GuardDeniedError,
    HandlerNotFoundError,
    InputSanitizationError,
    QuadkitError,
    SecurityError,
)


class TestEventsExceptionHierarchy:
    """Tests for events exception inheritance."""

    def test_event_error_inherits_from_quadkit(self) -> None:
        """EventError inherits from QuadkitError."""
        assert issubclass(EventError, QuadkitError)

    def test_handler_not_found_inherits_from_event(self) -> None:
        """HandlerNotFoundError inherits from EventError."""
        assert issubclass(HandlerNotFoundError, EventError)

    def test_duplicate_handler_inherits_from_event(self) -> None:
        """DuplicateHandlerError inherits from EventError."""
        assert issubclass(DuplicateHandlerError, EventError)


class TestEventsErrorCodes:
    """Tests for events exception error codes."""

    def test_event_error_has_code(self) -> None:
        """EventError has _code attribute."""
        exc = EventError()
        assert exc._code == "QK_ERR_EVT_001"

    def test_handler_not_found_has_code(self) -> None:
        """HandlerNotFoundError has _code."""
        exc = HandlerNotFoundError()
        assert exc._code == "QK_ERR_EVT_002"

    def test_duplicate_handler_has_code(self) -> None:
        """DuplicateHandlerError has _code."""
        exc = DuplicateHandlerError()
        assert exc._code == "QK_ERR_EVT_003"


class TestHandlerNotFoundError:
    """Tests for HandlerNotFoundError."""

    def test_can_specify_handler_type(self) -> None:
        """HandlerNotFoundError can specify handler type."""
        exc = HandlerNotFoundError(handler_type="UserCreatedHandler")
        assert "handler_type" in exc.details
        assert exc.details["handler_type"] == "UserCreatedHandler"

    def test_can_specify_message_type(self) -> None:
        """HandlerNotFoundError can specify message type."""
        exc = HandlerNotFoundError(message_type="UserCreated")
        assert "message_type" in exc.details
        assert exc.details["message_type"] == "UserCreated"

    def test_can_specify_both_types(self) -> None:
        """HandlerNotFoundError can specify both types."""
        exc = HandlerNotFoundError(
            handler_type="Handler",
            message_type="Message",
        )
        assert exc.details["handler_type"] == "Handler"
        assert exc.details["message_type"] == "Message"


class TestDuplicateHandlerError:
    """Tests for DuplicateHandlerError."""

    def test_can_specify_message_type(self) -> None:
        """DuplicateHandlerError can specify message type."""
        exc = DuplicateHandlerError(message_type="UserCreated")
        assert "message_type" in exc.details
        assert exc.details["message_type"] == "UserCreated"


class TestSecurityExceptionHierarchy:
    """Tests for security exception inheritance."""

    def test_security_error_inherits_from_quadkit(self) -> None:
        """SecurityError inherits from QuadkitError."""
        assert issubclass(SecurityError, QuadkitError)

    def test_guard_denied_inherits_from_security(self) -> None:
        """GuardDeniedError inherits from SecurityError."""
        assert issubclass(GuardDeniedError, SecurityError)

    def test_input_sanitization_inherits_from_security(self) -> None:
        """InputSanitizationError inherits from SecurityError."""
        assert issubclass(InputSanitizationError, SecurityError)

    def test_cors_violation_inherits_from_security(self) -> None:
        """CORSViolationError inherits from SecurityError."""
        assert issubclass(CORSViolationError, SecurityError)


class TestSecurityErrorCodes:
    """Tests for security exception error codes."""

    def test_security_error_has_code(self) -> None:
        """SecurityError has _code attribute."""
        exc = SecurityError()
        assert exc._code == "QK_ERR_SEC_001"

    def test_guard_denied_has_code(self) -> None:
        """GuardDeniedError has _code."""
        exc = GuardDeniedError()
        assert exc._code == "QK_ERR_SEC_002"

    def test_input_sanitization_has_code(self) -> None:
        """InputSanitizationError has _code."""
        exc = InputSanitizationError()
        assert exc._code == "QK_ERR_SEC_003"

    def test_cors_violation_has_code(self) -> None:
        """CORSViolationError has _code."""
        exc = CORSViolationError()
        assert exc._code == "QK_ERR_SEC_004"


class TestGuardDeniedError:
    """Tests for GuardDeniedError."""

    def test_can_specify_guard(self) -> None:
        """GuardDeniedError can specify guard."""
        exc = GuardDeniedError(guard="AdminGuard")
        assert exc.guard == "AdminGuard"

    def test_can_specify_reason(self) -> None:
        """GuardDeniedError can specify reason."""
        exc = GuardDeniedError(reason="User is not admin")
        assert exc.reason == "User is not admin"

    def test_can_specify_both(self) -> None:
        """GuardDeniedError can specify both guard and reason."""
        exc = GuardDeniedError(guard="RoleGuard", reason="Insufficient permissions")
        assert exc.guard == "RoleGuard"
        assert exc.reason == "Insufficient permissions"

    def test_guard_defaults_to_none(self) -> None:
        """GuardDeniedError guard defaults to None."""
        exc = GuardDeniedError()
        assert exc.guard is None

    def test_reason_defaults_to_none(self) -> None:
        """GuardDeniedError reason defaults to None."""
        exc = GuardDeniedError()
        assert exc.reason is None


class TestCORSViolationError:
    """Tests for CORSViolationError."""

    def test_can_specify_origin(self) -> None:
        """CORSViolationError can specify origin."""
        exc = CORSViolationError(origin="https://evil.com")
        assert exc.origin == "https://evil.com"

    def test_origin_defaults_to_none(self) -> None:
        """CORSViolationError origin defaults to None."""
        exc = CORSViolationError()
        assert exc.origin is None


class TestInputSanitizationError:
    """Tests for InputSanitizationError."""

    def test_has_default_message(self) -> None:
        """InputSanitizationError has descriptive default message."""
        exc = InputSanitizationError()
        assert "sanitization" in str(exc).lower()
