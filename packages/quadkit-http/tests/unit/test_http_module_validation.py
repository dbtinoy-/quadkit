"""HTTP lib helpers and validator tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.http.config import ConnectionPoolConfig, HTTPClientConfig
from quadkit.http.constants import (
    CONTENT_TYPE_JSON,
    DEFAULT_ENCODING,
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_TIMEOUT,
    GET,
    POST,
)
from quadkit.http.exceptions import (
    HTTPCircuitOpenError,
    HTTPClientError,
    HTTPConnectionError,
    HTTPInterceptorError,
    HTTPRetryExhaustedError,
    HTTPTimeoutError,
)
from quadkit.http.lib import (
    build_url,
    extract_json_type,
    format_timeout,
    merge_headers,
    parse_headers,
    parse_url_parts,
)
from quadkit.http.pool import ConnectionPool
from quadkit.http.types import RequestContext, ResponseContext
from quadkit.http.validation import (
    validate_host,
    validate_port,
    validate_positive_int,
    validate_timeout,
    validate_url,
)

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------




class TestBuildUrl:
    def test_simple_path(self) -> None:
        assert (
            build_url("http://api.example.com", "/users")
            == "http://api.example.com/users"
        )

    def test_trailing_slash_on_base(self) -> None:
        assert (
            build_url("http://api.example.com/", "/users")
            == "http://api.example.com/users"
        )

    def test_query_params(self) -> None:
        url = build_url("http://localhost", "/search", {"q": "hello", "page": 2})
        assert "q=hello" in url
        assert "page=2" in url

    def test_none_params_omitted(self) -> None:
        url = build_url("http://localhost", "/x", {"a": 1, "b": None})
        assert "b=" not in url
        assert "a=1" in url

    def test_no_path(self) -> None:
        assert build_url("http://example.com") == "http://example.com"


class TestParseHeaders:
    def test_lowercase_keys(self) -> None:
        result = parse_headers({"Content-Type": "application/json"})
        assert "content-type" in result
        assert "Content-Type" not in result

    def test_strip_values(self) -> None:
        result = parse_headers({"accept": "  */*  "})
        assert result["accept"] == "*/*"


class TestMergeHeaders:
    def test_later_wins(self) -> None:
        result = merge_headers({"a": "1"}, {"a": "2"})
        assert result["a"] == "2"

    def test_no_normalize(self) -> None:
        result = merge_headers({"X-Foo": "bar"}, normalize=False)
        assert "X-Foo" in result

    def test_normalize_by_default(self) -> None:
        result = merge_headers({"X-Foo": "bar"})
        assert "x-foo" in result


class TestFormatTimeout:
    def test_seconds_suffix(self) -> None:
        assert format_timeout(30.0) == "30.0s"

    def test_none_returns_no_timeout(self) -> None:
        assert format_timeout(None) == "no timeout"


class TestParseUrlParts:
    def test_full_url(self) -> None:
        parts = parse_url_parts("http://service.example.com:8080/api/v1")
        assert parts["scheme"] == "http"
        assert parts["host"] == "service.example.com"
        assert parts["port"] == 8080
        assert parts["path"] == "/api/v1"


class TestExtractJsonType:
    def test_json_content_type(self) -> None:
        assert extract_json_type("application/json") == "application/json"

    def test_json_with_charset(self) -> None:
        assert (
            extract_json_type("application/json; charset=utf-8") == "application/json"
        )

    def test_non_json(self) -> None:
        assert extract_json_type("text/html") is None

    def test_empty(self) -> None:
        assert extract_json_type("") is None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidateUrl:
    def test_valid_http(self) -> None:
        validate_url("http://example.com")

    def test_valid_https(self) -> None:
        validate_url("https://example.com:8080/path")

    @pytest.mark.parametrize("url", ["not-a-url", "http://", "", "://bad"])
    def test_invalid_raises_http_error(self, url: str) -> None:
        with pytest.raises(HTTPClientError):
            validate_url(url)


class TestValidateHost:
    def test_valid_hostname(self) -> None:
        validate_host("localhost")
        validate_host("example.com")

    def test_valid_ipv4(self) -> None:
        validate_host("192.168.1.1")

    def test_empty_raises(self) -> None:
        with pytest.raises(HTTPClientError):
            validate_host("")

    def test_double_dot_raises(self) -> None:
        with pytest.raises(HTTPClientError):
            validate_host("invalid..host")


class TestValidatePort:
    def test_valid_ports(self) -> None:
        validate_port(1)
        validate_port(8080)
        validate_port(65535)

    def test_zero_raises(self) -> None:
        with pytest.raises(HTTPClientError):
            validate_port(0)

    def test_too_large_raises(self) -> None:
        with pytest.raises(HTTPClientError):
            validate_port(70000)


class TestValidateTimeout:
    def test_valid_timeout(self) -> None:
        validate_timeout(5.0)
        validate_timeout(0.1)

    def test_none_is_allowed(self) -> None:
        validate_timeout(None)  # should not raise

    def test_zero_raises(self) -> None:
        with pytest.raises(HTTPClientError):
            validate_timeout(0)

    def test_negative_raises(self) -> None:
        with pytest.raises(HTTPClientError):
            validate_timeout(-1.0)


class TestValidatePositiveInt:
    def test_valid(self) -> None:
        validate_positive_int(1)
        validate_positive_int(100)

    def test_zero_raises(self) -> None:
        with pytest.raises(HTTPClientError):
            validate_positive_int(0)

    def test_negative_raises(self) -> None:
        with pytest.raises(HTTPClientError):
            validate_positive_int(-5)


# ---------------------------------------------------------------------------
# RequestContext / ResponseContext
# ---------------------------------------------------------------------------


