"""Tests for quadkit.http.validation (primitives and url)."""
from __future__ import annotations

import pytest

from quadkit.http.exceptions import HTTPClientError
from quadkit.http.validation.primitives import (
    validate_port,
    validate_positive_int,
    validate_timeout,
)
from quadkit.http.validation.url import validate_host, validate_url


class TestValidatePort:
    """Tests for validate_port."""

    def test_valid_port(self) -> None:
        """Valid ports pass."""
        validate_port(80)
        validate_port(443)
        validate_port(8080)
        validate_port(65535)
        validate_port(1)

    def test_port_0_raises(self) -> None:
        """Port 0 raises."""
        with pytest.raises(HTTPClientError, match="between 1 and 65535"):
            validate_port(0)

    def test_negative_port_raises(self) -> None:
        """Negative port raises."""
        with pytest.raises(HTTPClientError, match="between 1 and 65535"):
            validate_port(-1)

    def test_port_65536_raises(self) -> None:
        """Port 65536 raises (above max)."""
        with pytest.raises(HTTPClientError, match="between 1 and 65535"):
            validate_port(65536)

    def test_string_port_raises(self) -> None:
        """String port raises."""
        with pytest.raises(HTTPClientError, match="must be an integer"):
            validate_port("8080")  # type: ignore

    def test_none_port_raises(self) -> None:
        """None port raises."""
        with pytest.raises(HTTPClientError, match="must be an integer"):
            validate_port(None)  # type: ignore


class TestValidateTimeout:
    """Tests for validate_timeout."""

    def test_none_timeout(self) -> None:
        """None timeout passes."""
        validate_timeout(None)

    def test_valid_positive_float(self) -> None:
        """Positive float passes."""
        validate_timeout(5.0)
        validate_timeout(0.001)

    def test_valid_positive_int(self) -> None:
        """Positive int passes."""
        validate_timeout(30)

    def test_zero_timeout_raises(self) -> None:
        """Zero timeout raises."""
        with pytest.raises(HTTPClientError, match="must be positive"):
            validate_timeout(0)

    def test_negative_timeout_raises(self) -> None:
        """Negative timeout raises."""
        with pytest.raises(HTTPClientError, match="must be positive"):
            validate_timeout(-1.0)

    def test_string_timeout_raises(self) -> None:
        """String timeout raises."""
        with pytest.raises(HTTPClientError, match="must be a number"):
            validate_timeout("30")  # type: ignore


class TestValidatePositiveInt:
    """Tests for validate_positive_int."""

    def test_valid_positive_int(self) -> None:
        """Positive int passes."""
        validate_positive_int(1)
        validate_positive_int(100)

    def test_zero_raises(self) -> None:
        """Zero raises."""
        with pytest.raises(HTTPClientError, match="must be positive"):
            validate_positive_int(0)

    def test_negative_raises(self) -> None:
        """Negative raises."""
        with pytest.raises(HTTPClientError, match="must be positive"):
            validate_positive_int(-1)

    def test_string_raises(self) -> None:
        """String raises."""
        with pytest.raises(HTTPClientError, match="must be an integer"):
            validate_positive_int("100")  # type: ignore

    def test_custom_field_name(self) -> None:
        """Custom field name appears in error."""
        with pytest.raises(HTTPClientError, match="max_retries"):
            validate_positive_int(0, field="max_retries")


class TestValidateURL:
    """Tests for validate_url."""

    def test_valid_https_url(self) -> None:
        """Valid https URL passes."""
        validate_url("https://api.example.com")
        validate_url("https://api.example.com/users/123")

    def test_valid_http_url(self) -> None:
        """Valid http URL passes."""
        validate_url("http://localhost:8080")
        validate_url("http://127.0.0.1/")

    def test_valid_url_without_scheme(self) -> None:
        """URL without scheme passes when require_scheme=False."""
        validate_url("api.example.com/users", require_scheme=False)

    def test_empty_string_raises(self) -> None:
        """Empty string raises."""
        with pytest.raises(HTTPClientError, match="non-empty"):
            validate_url("")

    def test_none_raises(self) -> None:
        """None raises."""
        with pytest.raises(HTTPClientError, match="non-empty"):
            validate_url(None)  # type: ignore

    def test_missing_scheme_raises(self) -> None:
        """URL without scheme raises when require_scheme=True."""
        with pytest.raises(HTTPClientError, match="scheme"):
            validate_url("api.example.com")

    def test_url_without_host_or_path_raises(self) -> None:
        """URL with no host and no path raises."""
        with pytest.raises(HTTPClientError, match="hostname"):
            validate_url("https://", require_scheme=False)

    def test_url_with_query_params(self) -> None:
        """URL with query params passes."""
        validate_url("https://api.example.com?page=1&size=10")

    def test_url_with_fragment(self) -> None:
        """URL with fragment passes."""
        validate_url("https://api.example.com#section")

    def test_url_with_port(self) -> None:
        """URL with port passes."""
        validate_url("https://api.example.com:8443/api")

    def test_url_with_auth(self) -> None:
        """URL with auth passes."""
        validate_url("https://user:pass@example.com/api")


class TestValidateHost:
    """Tests for validate_host."""

    def test_valid_hostname(self) -> None:
        """Valid hostname passes."""
        validate_host("api.example.com")
        validate_host("example.com")

    def test_hostname_with_dash(self) -> None:
        """Hostname with dashes passes."""
        validate_host("my-api.example.com")

    def test_valid_ipv4(self) -> None:
        """Valid IPv4 addresses pass."""
        validate_host("192.168.1.1")
        validate_host("10.0.0.1")
        validate_host("255.255.255.255")

    def test_empty_string_raises(self) -> None:
        """Empty string raises."""
        with pytest.raises(HTTPClientError, match="non-empty"):
            validate_host("")

    def test_none_raises(self) -> None:
        """None raises."""
        with pytest.raises(HTTPClientError, match="non-empty"):
            validate_host(None)  # type: ignore

    def test_localhost(self) -> None:
        """Localhost passes."""
        validate_host("localhost")

    def test_invalid_hostname_raises(self) -> None:
        """Invalid hostname raises."""
        with pytest.raises(HTTPClientError, match="Invalid hostname"):
            validate_host("!!!invalid!!!")
