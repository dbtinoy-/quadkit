"""Tests for middleware exceptions."""

from quadkit.middleware.exceptions import (
    MiddlewareError,
    MiddlewareExecutionError,
)


class TestMiddlewareError:
    """Tests for MiddlewareError."""

    def test_middleware_error_instantiation(self) -> None:
        """Should instantiate with message."""
        error = MiddlewareError("Middleware error")
        assert "Middleware error" in str(error)


class TestMiddlewareExecutionError:
    """Tests for MiddlewareExecutionError."""

    def test_middleware_execution_error(self) -> None:
        """Should instantiate."""
        error = MiddlewareExecutionError("Middleware execution failed")
        assert "Middleware execution failed" in str(error)
