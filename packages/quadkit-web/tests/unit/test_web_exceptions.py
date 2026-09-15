"""Tests for web exceptions."""

from quadkit.web.exceptions import (
    BadRequestError,
    ConflictError,
    DependencyResolutionError,
    ForbiddenError,
    HTTPError,
    InternalServerError,
    MethodNotAllowedError,
    NotFoundError,
    RateLimitError,
    TooManyConnectionsError,
    UnauthorizedError,
    UnprocessableEntityError,
)
from quadkit.contracts.data.sql.database import DatabaseProviderProtocol


class TestHTTPError:
    """Tests for HTTPError."""

    def test_http_error_basic(self) -> None:
        """Should instantiate with status code and detail."""
        error = HTTPError(500, "Internal server error")
        assert error.status_code == 500
        assert "Internal server error" in str(error)

    def test_http_error_with_headers(self) -> None:
        """Should support custom headers."""
        error = HTTPError(400, "Bad request", headers={"X-Custom": "value"})
        assert error.headers["X-Custom"] == "value"

    def test_http_error_with_cause(self) -> None:
        """Should support cause exception."""
        cause = ValueError("Original error")
        error = HTTPError(500, "Error", cause=cause)
        assert error.__cause__ is cause


class TestNotFoundError:
    """Tests for NotFoundError."""

    def test_not_found_error(self) -> None:
        """Should instantiate with 404."""
        error = NotFoundError("Resource not found")
        assert error.status_code == 404
        assert "Resource not found" in str(error)

    def test_not_found_default_message(self) -> None:
        """Should have default message."""
        error = NotFoundError()
        assert "Not Found" in str(error)


class TestBadRequestError:
    """Tests for BadRequestError."""

    def test_bad_request_error(self) -> None:
        """Should instantiate with 400."""
        error = BadRequestError("Invalid input")
        assert error.status_code == 400
        assert "Invalid input" in str(error)


class TestUnauthorizedError:
    """Tests for UnauthorizedError."""

    def test_unauthorized_error(self) -> None:
        """Should instantiate with 401."""
        error = UnauthorizedError("Authentication required")
        assert error.status_code == 401
        assert "Authentication required" in str(error)


class TestForbiddenError:
    """Tests for ForbiddenError."""

    def test_forbidden_error(self) -> None:
        """Should instantiate with 403."""
        error = ForbiddenError("Access denied")
        assert error.status_code == 403
        assert "Access denied" in str(error)


class TestMethodNotAllowedError:
    """Tests for MethodNotAllowedError."""

    def test_method_not_allowed_error(self) -> None:
        """Should instantiate with 405."""
        error = MethodNotAllowedError("Use GET instead")
        assert error.status_code == 405
        assert "Use GET instead" in str(error)


class TestConflictError:
    """Tests for ConflictError."""

    def test_conflict_error(self) -> None:
        """Should instantiate with 409."""
        error = ConflictError("Resource already exists")
        assert error.status_code == 409
        assert "Resource already exists" in str(error)


class TestUnprocessableEntityError:
    """Tests for UnprocessableEntityError."""

    def test_unprocessable_entity_error(self) -> None:
        """Should instantiate with 422."""
        error = UnprocessableEntityError("Invalid entity data")
        assert error.status_code == 422
        assert "Invalid entity data" in str(error)


class TestInternalServerError:
    """Tests for InternalServerError."""

    def test_internal_server_error(self) -> None:
        """Should instantiate with 500."""
        error = InternalServerError("Something went wrong")
        assert error.status_code == 500
        assert "Something went wrong" in str(error)

    def test_internal_server_error_custom_code(self) -> None:
        """Should support custom error code."""
        error = InternalServerError("Error", code="CUSTOM_ERROR")
        assert error.code == "CUSTOM_ERROR"


class TestDependencyResolutionError:
    """Tests for DependencyResolutionError."""

    def test_dependency_resolution_error(self) -> None:
        """Should include param and service type info."""
        error = DependencyResolutionError("db", DatabaseProviderProtocol)
        assert error.status_code == 500
        assert "db" in error.detail
        assert error.param == "db"


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_rate_limit_error(self) -> None:
        """Should instantiate with 429."""
        error = RateLimitError("Too many requests")
        assert error.status_code == 429

    def test_rate_limit_error_retry_after(self) -> None:
        """Should include Retry-After header."""
        error = RateLimitError("Too many requests", retry_after=60)
        assert error.headers["Retry-After"] == "60"


class TestTooManyConnectionsError:
    """Tests for TooManyConnectionsError."""

    def test_too_many_connections_error(self) -> None:
        """Should instantiate with 503."""
        error = TooManyConnectionsError("Connection limit reached")
        assert error.status_code == 503
        assert "Connection limit reached" in str(error)
