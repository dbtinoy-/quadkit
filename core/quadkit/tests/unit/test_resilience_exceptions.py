"""Tests for resilience exceptions from contracts."""

from quadkit.contracts.exceptions import (
    BulkheadError,
    CircuitBreakerError,
    CircuitOpenError,
    FallbackError,
    QuadkitError,
    ResilienceError,
    RetryError,
    RetryExhaustedError,
)


class TestResilienceExceptionHierarchy:
    """Tests for resilience exception inheritance."""

    def test_resilience_error_inherits_from_quadkit(self) -> None:
        """ResilienceError inherits from QuadkitError."""
        assert issubclass(ResilienceError, QuadkitError)

    def test_all_resilience_errors_inherit(self) -> None:
        """All resilience exceptions inherit from ResilienceError."""
        assert issubclass(RetryError, ResilienceError)
        assert issubclass(CircuitBreakerError, ResilienceError)
        assert issubclass(BulkheadError, ResilienceError)
        assert issubclass(FallbackError, ResilienceError)

    def test_retry_exhausted_inherits_from_retry(self) -> None:
        """RetryExhaustedError inherits from RetryError."""
        assert issubclass(RetryExhaustedError, RetryError)

    def test_circuit_open_inherits_from_circuit_breaker(self) -> None:
        """CircuitOpenError inherits from CircuitBreakerError."""
        assert issubclass(CircuitOpenError, CircuitBreakerError)


class TestResilienceErrorCodes:
    """Tests for resilience exception error codes."""

    def test_resilience_error_has_code(self) -> None:
        """ResilienceError has _code attribute."""
        exc = ResilienceError()
        assert exc._code == "QK_ERR_RES_001"

    def test_retry_error_has_code(self) -> None:
        """RetryError has _code."""
        exc = RetryError()
        assert exc._code == "QK_ERR_RES_002"

    def test_circuit_breaker_error_has_code(self) -> None:
        """CircuitBreakerError has _code."""
        exc = CircuitBreakerError()
        assert exc._code == "QK_ERR_RES_003"

    def test_bulkhead_error_has_code(self) -> None:
        """BulkheadError has _code."""
        exc = BulkheadError()
        assert exc._code == "QK_ERR_RES_004"

    def test_fallback_error_has_code(self) -> None:
        """FallbackError has _code."""
        exc = FallbackError()
        assert exc._code == "QK_ERR_RES_005"

    def test_retry_exhausted_error_has_code(self) -> None:
        """RetryExhaustedError has _code."""
        exc = RetryExhaustedError()
        assert exc._code == "QK_ERR_RES_006"

    def test_circuit_open_error_has_code(self) -> None:
        """CircuitOpenError has _code."""
        exc = CircuitOpenError()
        assert exc._code == "QK_ERR_RES_007"


class TestRetryExhaustedError:
    """Tests for RetryExhaustedError."""

    def test_stores_attempts(self) -> None:
        """RetryExhaustedError stores attempt count."""
        exc = RetryExhaustedError(attempts=5)
        assert exc.attempts == 5

    def test_default_attempts_is_zero(self) -> None:
        """RetryExhaustedError defaults attempts to 0."""
        exc = RetryExhaustedError()
        assert exc.attempts == 0

    def test_attempts_in_details(self) -> None:
        """RetryExhaustedError includes attempts in details."""
        exc = RetryExhaustedError(attempts=3)
        assert "attempts" in exc.details
        assert exc.details["attempts"] == 3


class TestCircuitOpenError:
    """Tests for CircuitOpenError."""

    def test_has_default_message(self) -> None:
        """CircuitOpenError has descriptive default message."""
        exc = CircuitOpenError()
        assert "circuit" in str(exc).lower()
        assert "open" in str(exc).lower()


class TestBulkheadError:
    """Tests for BulkheadError."""

    def test_has_default_message(self) -> None:
        """BulkheadError has descriptive default message."""
        exc = BulkheadError()
        assert "bulkhead" in str(exc).lower()
        assert "rejected" in str(exc).lower()
