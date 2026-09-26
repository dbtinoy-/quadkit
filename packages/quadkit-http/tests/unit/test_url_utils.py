"""Tests for HTTP URL utilities."""

from __future__ import annotations

import pytest

from quadkit.http.lib.url import build_url, parse_url_parts


class TestBuildURL:
    """Tests for build_url."""

    def test_simple_url(self) -> None:
        """Build URL without path or params."""
        assert build_url("https://api.example.com") == "https://api.example.com"

    def test_with_path(self) -> None:
        """Build URL with path."""
        assert build_url("https://api.example.com", "/users") == "https://api.example.com/users"

    def test_with_params(self) -> None:
        """Build URL with query params."""
        result = build_url("https://api.example.com", params={"page": 1})
        assert result == "https://api.example.com?page=1"

    def test_with_path_and_params(self) -> None:
        """Build URL with both path and params."""
        result = build_url("https://api.example.com", "/users", {"page": 1})
        assert result == "https://api.example.com/users?page=1"

    def test_params_none_filtered(self) -> None:
        """None values in params are omitted."""
        result = build_url("https://api.example.com", params={"a": 1, "b": None})
        assert result == "https://api.example.com?a=1"

    def test_all_params_none(self) -> None:
        """All None params results in URL without query."""
        result = build_url("https://api.example.com", params={"a": None})
        assert result == "https://api.example.com"

    def test_trailing_slash_base(self) -> None:
        """Trailing slash on base is handled."""
        result = build_url("https://api.example.com/", "/users")
        assert result == "https://api.example.com/users"

    def test_no_slash_path(self) -> None:
        """Path without leading slash is handled."""
        result = build_url("https://api.example.com", "users")
        assert result == "https://api.example.com/users"

    def test_multiple_params(self) -> None:
        """Multiple query params work."""
        result = build_url("https://api.example.com", params={"a": 1, "b": 2})
        assert "a=1" in result and "b=2" in result


class TestParseURLParts:
    """Tests for parse_url_parts."""

    def test_simple_url(self) -> None:
        """Parse simple URL."""
        result = parse_url_parts("https://api.example.com")
        assert result["scheme"] == "https"
        assert result["host"] == "api.example.com"
        assert result["port"] is None

    def test_with_port(self) -> None:
        """Parse URL with port."""
        result = parse_url_parts("https://api.example.com:8443")
        assert result["port"] == 8443

    def test_with_path(self) -> None:
        """Parse URL with path."""
        result = parse_url_parts("https://api.example.com/users/123")
        assert result["path"] == "/users/123"

    def test_with_query(self) -> None:
        """Parse URL with query string."""
        result = parse_url_parts("https://api.example.com?page=1")
        assert result["params"] == {"page": ["1"]}

    def test_with_fragment(self) -> None:
        """Parse URL with fragment."""
        result = parse_url_parts("https://api.example.com#section")
        assert result["fragment"] == "section"

    def test_full_url(self) -> None:
        """Parse full URL with all parts."""
        result = parse_url_parts("https://api.example.com:8443/users?page=1#section")
        assert result["scheme"] == "https"
        assert result["host"] == "api.example.com"
        assert result["port"] == 8443
        assert result["path"] == "/users"
        assert result["params"] == {"page": ["1"]}
        assert result["fragment"] == "section"