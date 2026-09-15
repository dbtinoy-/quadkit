"""Tests for HTTP constants."""

import pytest

from quadkit.contracts.web.http_constants import (
    CONTENT_TYPE_BYTES,
    CONTENT_TYPE_FORM,
    CONTENT_TYPE_HTML,
    CONTENT_TYPE_JSON,
    CONTENT_TYPE_MULTIPART,
    CONTENT_TYPE_TEXT,
    DEFAULT_ENCODING,
    DELETE,
    GET,
    HEAD,
    HEADER_ACCEPT,
    HEADER_AUTHORIZATION,
    HEADER_CONTENT_TYPE,
    HEADER_USER_AGENT,
    HEADER_X_REQUEST_ID,
    OPTIONS,
    PATCH,
    POST,
    PUT,
)


class TestHttpMethods:
    """Tests for HTTP method constants."""

    def test_get_method(self) -> None:
        """Test GET method."""
        assert GET == "GET"

    def test_post_method(self) -> None:
        """Test POST method."""
        assert POST == "POST"

    def test_put_method(self) -> None:
        """Test PUT method."""
        assert PUT == "PUT"

    def test_delete_method(self) -> None:
        """Test DELETE method."""
        assert DELETE == "DELETE"

    def test_patch_method(self) -> None:
        """Test PATCH method."""
        assert PATCH == "PATCH"

    def test_head_method(self) -> None:
        """Test HEAD method."""
        assert HEAD == "HEAD"

    def test_options_method(self) -> None:
        """Test OPTIONS method."""
        assert OPTIONS == "OPTIONS"


class TestContentTypes:
    """Tests for content type constants."""

    def test_content_type_json(self) -> None:
        """Test JSON content type."""
        assert CONTENT_TYPE_JSON == "application/json"

    def test_content_type_form(self) -> None:
        """Test form content type."""
        assert CONTENT_TYPE_FORM == "application/x-www-form-urlencoded"

    def test_content_type_text(self) -> None:
        """Test text content type."""
        assert CONTENT_TYPE_TEXT == "text/plain"

    def test_content_type_html(self) -> None:
        """Test HTML content type."""
        assert CONTENT_TYPE_HTML == "text/html"

    def test_content_type_multipart(self) -> None:
        """Test multipart content type."""
        assert CONTENT_TYPE_MULTIPART == "multipart/form-data"

    def test_content_type_bytes(self) -> None:
        """Test bytes content type."""
        assert CONTENT_TYPE_BYTES == "application/octet-stream"


class TestHeaderNames:
    """Tests for header name constants."""

    def test_header_content_type(self) -> None:
        """Test content-type header."""
        assert HEADER_CONTENT_TYPE == "content-type"

    def test_header_authorization(self) -> None:
        """Test authorization header."""
        assert HEADER_AUTHORIZATION == "authorization"

    def test_header_accept(self) -> None:
        """Test accept header."""
        assert HEADER_ACCEPT == "accept"

    def test_header_user_agent(self) -> None:
        """Test user-agent header."""
        assert HEADER_USER_AGENT == "user-agent"

    def test_header_x_request_id(self) -> None:
        """Test x-request-id header."""
        assert HEADER_X_REQUEST_ID == "x-request-id"


class TestDefaultEncoding:
    """Tests for default encoding constant."""

    def test_default_encoding(self) -> None:
        """Test default encoding is UTF-8."""
        assert DEFAULT_ENCODING == "utf-8"
