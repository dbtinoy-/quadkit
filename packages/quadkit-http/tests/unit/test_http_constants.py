"""Unit tests for quadkit.http.constants."""

from __future__ import annotations

import pytest
from quadkit.http import constants


class TestVersion:
    """Tests for __version__ constant."""

    def test_version_is_string(self) -> None:
        """Test version is a string."""
        assert isinstance(constants.__version__, str)

    def test_version_is_not_empty(self) -> None:
        """Test version is not empty."""
        assert len(constants.__version__) > 0


class TestEnvConfig:
    """Tests for environment variable configuration constants."""

    def test_env_prefix(self) -> None:
        """Test ENV_PREFIX is correct."""
        assert constants.ENV_PREFIX == "QK_HTTP__"

    def test_env_nested_delimiter(self) -> None:
        """Test ENV_NESTED_DELIMITER is correct."""
        assert constants.ENV_NESTED_DELIMITER == "__"


class TestHttpMethods:
    """Tests for HTTP method constants."""

    def test_get(self) -> None:
        """Test GET method constant."""
        assert constants.GET == "GET"

    def test_post(self) -> None:
        """Test POST method constant."""
        assert constants.POST == "POST"

    def test_put(self) -> None:
        """Test PUT method constant."""
        assert constants.PUT == "PUT"

    def test_patch(self) -> None:
        """Test PATCH method constant."""
        assert constants.PATCH == "PATCH"

    def test_delete(self) -> None:
        """Test DELETE method constant."""
        assert constants.DELETE == "DELETE"

    def test_head(self) -> None:
        """Test HEAD method constant."""
        assert constants.HEAD == "HEAD"

    def test_options(self) -> None:
        """Test OPTIONS method constant."""
        assert constants.OPTIONS == "OPTIONS"


class TestContentTypes:
    """Tests for Content-Type constants."""

    def test_content_type_json(self) -> None:
        """Test JSON content type."""
        assert constants.CONTENT_TYPE_JSON == "application/json"

    def test_content_type_text(self) -> None:
        """Test text content type."""
        assert constants.CONTENT_TYPE_TEXT == "text/plain"

    def test_content_type_html(self) -> None:
        """Test HTML content type."""
        assert constants.CONTENT_TYPE_HTML == "text/html"

    def test_content_type_form(self) -> None:
        """Test form content type."""
        assert constants.CONTENT_TYPE_FORM == "application/x-www-form-urlencoded"

    def test_content_type_multipart(self) -> None:
        """Test multipart content type."""
        assert constants.CONTENT_TYPE_MULTIPART == "multipart/form-data"

    def test_content_type_bytes(self) -> None:
        """Test bytes content type."""
        assert constants.CONTENT_TYPE_BYTES == "application/octet-stream"


class TestHeaderNames:
    """Tests for HTTP header name constants."""

    def test_header_accept(self) -> None:
        """Test Accept header."""
        assert constants.HEADER_ACCEPT == "accept"

    def test_header_content_type(self) -> None:
        """Test Content-Type header."""
        assert constants.HEADER_CONTENT_TYPE == "content-type"

    def test_header_authorization(self) -> None:
        """Test Authorization header."""
        assert constants.HEADER_AUTHORIZATION == "authorization"

    def test_header_user_agent(self) -> None:
        """Test User-Agent header."""
        assert constants.HEADER_USER_AGENT == "user-agent"

    def test_header_x_request_id(self) -> None:
        """Test X-Request-ID header."""
        assert constants.HEADER_X_REQUEST_ID == "x-request-id"


class TestEncoding:
    """Tests for encoding constants."""

    def test_default_encoding(self) -> None:
        """Test default encoding is utf-8."""
        assert constants.DEFAULT_ENCODING == "utf-8"


class TestConnectionPoolDefaults:
    """Tests for connection pool default constants."""

    def test_default_max_connections(self) -> None:
        """Test DEFAULT_MAX_CONNECTIONS."""
        assert constants.DEFAULT_MAX_CONNECTIONS == 10

    def test_default_max_keepalive_connections(self) -> None:
        """Test DEFAULT_MAX_KEEPALIVE_CONNECTIONS."""
        assert constants.DEFAULT_MAX_KEEPALIVE_CONNECTIONS == 5

    def test_default_max_connections_per_host(self) -> None:
        """Test DEFAULT_MAX_CONNECTIONS_PER_HOST."""
        assert constants.DEFAULT_MAX_CONNECTIONS_PER_HOST == 10

    def test_default_timeout(self) -> None:
        """Test DEFAULT_TIMEOUT."""
        assert constants.DEFAULT_TIMEOUT == 30.0

    def test_default_ttl_dns_cache(self) -> None:
        """Test DEFAULT_TTL_DNS_CACHE."""
        assert constants.DEFAULT_TTL_DNS_CACHE == 300