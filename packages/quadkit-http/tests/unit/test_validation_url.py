"""Tests for quadkit.http.validation.url."""

from __future__ import annotations

import pytest

from quadkit.http.exceptions import HTTPClientError
from quadkit.http.validation.url import validate_host, validate_url


class TestValidateURL:
    """Tests for validate_url."""

    def test_valid_https_url(self) -> None:
        """Valid https URL passes."""
        validate_url("https://api.example.com")
        validate_url("https://api.example.com/")
        validate_url("https://api.example.com/users/123")

    def test_valid_http_url(self) -> None:
        """Valid http URL passes."""
        validate_url("http://localhost:8080")
        validate_url("http://127.0.0.1/")

    def test_valid_url_without_scheme(self) -> None:
        """URL without scheme passes when require_scheme=False."""
        validate_url("api.example.com/users", require_scheme=False)
        validate_url("example.com", require_scheme=False)

    def test_empty_string_raises(self) -> None:
        """Empty string raises HTTPClientError."""
        with pytest.raises(HTTPClientError, match="non-empty"):
            validate_url("")

    def test_none_raises(self) -> None:
        """None raises HTTPClientError."""
        with pytest.raises(HTTPClientError, match="non-empty"):
            validate_url(None)  # type: ignore

    def test_non_string_raises(self) -> None:
        """Non-string raises HTTPClientError."""
        with pytest.raises(HTTPClientError, match="non-empty"):
            validate_url(123)  # type: ignore

    def test_missing_scheme_raises(self) -> None:
        """URL without scheme raises when require_scheme=True."""
        with pytest.raises(HTTPClientError, match="scheme"):
            validate_url("api.example.com")

    def test_scheme_required(self) -> None:
        """Any scheme passes validation (scheme presence only)."""
        validate_url("ftp://example.com")
        validate_url("file://example.com")

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

    def test_malformed_url_raises(self) -> None:
        """Malformed URL raises."""
        with pytest.raises(HTTPClientError, match="Invalid URL format"):
            validate_url("https://[invalid")

    def test_localhost(self) -> None:
        """Localhost passes."""
        validate_url("http://localhost/api")
        validate_url("http://localhost:3000")

    def test_ipv6_address(self) -> None:
        """IPv6 address is accepted."""
        validate_url("http://[::1]/api")

    def test_file_url(self) -> None:
        """file:// scheme passes when require_scheme=False."""
        validate_url("file:///path/to/file", require_scheme=False)


class TestValidateHost:
    """Tests for validate_host."""

    def test_valid_hostname(self) -> None:
        """Valid hostname passes."""
        validate_host("api.example.com")
        validate_host("example.com")
        validate_host("my-api.service.local")

    def test_hostname_with_dash(self) -> None:
        """Hostname with dashes passes."""
        validate_host("my-api.example.com")

    def test_hostname_with_numbers(self) -> None:
        """Hostname with numbers passes."""
        validate_host("api2.example.com")
        validate_host("3com.com")

    def test_valid_ipv4(self) -> None:
        """Valid IPv4 addresses pass."""
        validate_host("192.168.1.1")
        validate_host("10.0.0.1")
        validate_host("172.16.0.1")
        validate_host("0.0.0.0")
        validate_host("255.255.255.255")

    def test_ipv4_edge_cases(self) -> None:
        """Edge case IPv4 addresses pass."""
        validate_host("127.0.0.1")
        validate_host("0.0.0.0")
        validate_host("1.2.3.4")

    def test_short_ipv4_format(self) -> None:
        """Short IPv4 format passes."""
        validate_host("1.2.3")
        validate_host("1.2")

    def test_empty_string_raises(self) -> None:
        """Empty string raises."""
        with pytest.raises(HTTPClientError, match="non-empty"):
            validate_host("")

    def test_none_raises(self) -> None:
        """None raises."""
        with pytest.raises(HTTPClientError, match="non-empty"):
            validate_host(None)  # type: ignore

    def test_non_string_raises(self) -> None:
        """Non-string raises."""
        with pytest.raises(HTTPClientError, match="non-empty"):
            validate_host(123)  # type: ignore

    def test_localhost(self) -> None:
        """Localhost passes."""
        validate_host("localhost")

    def test_subdomain(self) -> None:
        """Subdomain passes."""
        validate_host("api.v2.example.com")
        validate_host("a.b.c.d.example.com")