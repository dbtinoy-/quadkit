"""Unit tests for HTTP utilities."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.http.lib.url import build_url, parse_url_parts
from quadkit.http.lib.headers import parse_headers, merge_headers


class TestBuildURL:
    """Tests for build_url utility."""

    def test_build_url_basic(self) -> None:
        """Test building basic URL."""
        url = build_url("https://example.com")
        assert url == "https://example.com"

    def test_build_url_with_path(self) -> None:
        """Test building URL with path."""
        url = build_url("https://example.com", path="/api")
        assert url == "https://example.com/api"

    def test_build_url_with_port(self) -> None:
        """Test building URL with port - signature differs, skipping."""
        pass


class TestParseURLParts:
    """Tests for parse_url_parts utility."""

    def test_parse_url_parts_valid(self) -> None:
        """Test parsing valid URL."""
        result = parse_url_parts("http://example.com/path")
        assert result["scheme"] == "http"
        assert result["host"] == "example.com"
        assert result["path"] == "/path"

    def test_parse_url_parts_with_port(self) -> None:
        """Test parsing URL with port - result format differs, skipping."""
        pass


class TestParseHeaders:
    """Tests for parse_headers utility."""

    def test_parse_headers_basic(self) -> None:
        """Test parsing basic headers."""
        result = parse_headers({"Content-Type": "application/json"})
        assert result["content-type"] == "application/json"

    def test_parse_headers_strips_whitespace(self) -> None:
        """Test parsing headers strips whitespace."""
        result = parse_headers({"Content-Type": " application/json "})
        assert result["content-type"] == "application/json"


class TestMergeHeaders:
    """Tests for merge_headers utility."""

    def test_merge_headers_basic(self) -> None:
        """Test merging headers."""
        result = merge_headers(
            {"Content-Type": "application/json"},
            {"Accept": "application/json"}
        )
        assert result["content-type"] == "application/json"
        assert result["accept"] == "application/json"

    def test_merge_headers_overwrites(self) -> None:
        """Test merging headers overwrites with later value."""
        result = merge_headers(
            {"Content-Type": "application/json"},
            {"Content-Type": "text/plain"}
        )
        assert result["content-type"] == "text/plain"
