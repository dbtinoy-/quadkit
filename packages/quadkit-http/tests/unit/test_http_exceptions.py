"""Unit tests for quadkit-http exceptions.

These tests verify the exception hierarchy in quadkit.http.exceptions.
"""

from unittest.mock import MagicMock

from quadkit.contracts.exceptions import InfrastructureError
from quadkit.http.exceptions import (
    HTTPCircuitOpenError,
    HTTPClientError,
    HTTPConnectionError,
    HTTPInterceptorError,
    HTTPRetryExhaustedError,
    HTTPStatusError,
    HTTPTimeoutError,
    HTTPUnsafeURLError,
)


class TestHttpExceptionHierarchy:
    """Tests for HTTP exception hierarchy."""

    def test_http_client_error_inherits_from_infrastructure_error(self) -> None:
        assert issubclass(HTTPClientError, InfrastructureError)

    def test_http_connection_error_inherits_from_http_client_error(self) -> None:
        assert issubclass(HTTPConnectionError, HTTPClientError)

    def test_http_timeout_error_inherits_from_http_client_error(self) -> None:
        assert issubclass(HTTPTimeoutError, HTTPClientError)

    def test_http_interceptor_error_inherits_from_http_client_error(self) -> None:
        assert issubclass(HTTPInterceptorError, HTTPClientError)

    def test_http_circuit_open_error_inherits_from_http_client_error(self) -> None:
        assert issubclass(HTTPCircuitOpenError, HTTPClientError)

    def test_http_retry_exhausted_error_inherits_from_http_client_error(self) -> None:
        assert issubclass(HTTPRetryExhaustedError, HTTPClientError)

    def test_http_status_error_inherits_from_http_client_error(self) -> None:
        assert issubclass(HTTPStatusError, HTTPClientError)

    def test_http_unsafe_url_error_inherits_from_http_client_error(self) -> None:
        assert issubclass(HTTPUnsafeURLError, HTTPClientError)


class TestHTTPUnsafeURLError:
    """Tests for HTTPUnsafeURLError."""

    def test_http_unsafe_url_error_code(self) -> None:
        error = HTTPUnsafeURLError("blocked")
        assert error._code == "QK_ERR_HTTP_008"

    def test_http_unsafe_url_error_default_message(self) -> None:
        error = HTTPUnsafeURLError("Unsafe URL rejected")
        assert error.message == "Unsafe URL rejected"


class TestHTTPClientError:
    """Tests for HTTPClientError."""

    def test_http_client_error_default_message(self) -> None:
        error = HTTPClientError()
        assert error.message is not None


class TestHTTPConnectionError:
    """Tests for HTTPConnectionError."""

    def test_http_connection_error_default_message(self) -> None:
        error = HTTPConnectionError()
        assert error.message is not None


class TestHTTPTimeoutError:
    """Tests for HTTPTimeoutError."""

    def test_http_timeout_error_default_message(self) -> None:
        error = HTTPTimeoutError()
        assert error.message is not None


class TestHTTPInterceptorError:
    """Tests for HTTPInterceptorError."""

    def test_http_interceptor_error_default_message(self) -> None:
        error = HTTPInterceptorError()
        assert error.message is not None


class TestHTTPCircuitOpenError:
    """Tests for HTTPCircuitOpenError."""

    def test_http_circuit_open_error_default_message(self) -> None:
        error = HTTPCircuitOpenError()
        assert error.message is not None


class TestHTTPRetryExhaustedError:
    """Tests for HTTPRetryExhaustedError."""

    def test_http_retry_exhausted_error_default_message(self) -> None:
        error = HTTPRetryExhaustedError()
        assert error.message is not None


class TestHTTPStatusError:
    """Tests for HTTPStatusError."""

    def test_http_status_error_attributes(self) -> None:
        mock_response = MagicMock()
        mock_response.url = "https://example.com/api"

        error = HTTPStatusError(status=404, response=mock_response)
        assert error.status == 404
        assert error.response == mock_response

    def test_http_status_error_custom_message(self) -> None:
        mock_response = MagicMock()
        mock_response.url = "https://example.com/api"

        error = HTTPStatusError(
            status=500, response=mock_response, message="Server error"
        )
        assert error.message == "Server error"

    def test_http_status_error_default_message(self) -> None:
        mock_response = MagicMock()
        mock_response.url = "https://example.com/api"

        error = HTTPStatusError(status=400, response=mock_response)
        assert "400" in error.message

    def test_http_status_error_repr(self) -> None:
        mock_response = MagicMock()
        mock_response.url = "https://example.com/api"

        error = HTTPStatusError(status=404, response=mock_response)
        repr_str = repr(error)
        assert "status=404" in repr_str
        assert "example.com/api" in repr_str


class TestExceptionAllExports:
    """Tests to verify __all__ exports."""

    def test_all_contains_all_exceptions(self) -> None:
        from quadkit.http import exceptions as exc_module

        expected = [
            "HTTPCircuitOpenError",
            "HTTPClientError",
            "HTTPConnectionError",
            "HTTPInterceptorError",
            "HTTPRetryExhaustedError",
            "HTTPStatusError",
            "HTTPTimeoutError",
            "HTTPUnsafeURLError",
        ]
        for item in expected:
            assert item in exc_module.__all__
