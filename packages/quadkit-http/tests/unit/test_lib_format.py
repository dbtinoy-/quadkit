"""Tests for quadkit.http.lib.format."""

from __future__ import annotations

import pytest

from quadkit.http.lib.format import extract_json_type, format_timeout


class TestFormatTimeout:
    """Tests for format_timeout."""

    def test_none_returns_no_timeout(self) -> None:
        """None returns 'no timeout'."""
        result = format_timeout(None)
        assert result == "no timeout"

    def test_integer_seconds(self) -> None:
        """Integer seconds formats with s suffix."""
        result = format_timeout(30)
        assert result == "30s"

    def test_float_seconds(self) -> None:
        """Float seconds formats correctly."""
        result = format_timeout(5.5)
        assert result == "5.5s"

    def test_large_timeout(self) -> None:
        """Large timeouts format correctly."""
        result = format_timeout(3600.0)
        assert result == "3600.0s"

    def test_small_timeout(self) -> None:
        """Small timeouts format correctly."""
        result = format_timeout(0.001)
        assert result == "0.001s"

    def test_zero_timeout(self) -> None:
        """Zero formats as '0s'."""
        result = format_timeout(0)
        assert result == "0s"

    def test_negative_timeout(self) -> None:
        """Negative timeout formats (edge case)."""
        result = format_timeout(-5.0)
        assert result == "-5.0s"


class TestExtractJSONType:
    """Tests for extract_json_type."""

    def test_simple_json(self) -> None:
        """Simple application/json returns itself."""
        result = extract_json_type("application/json")
        assert result == "application/json"

    def test_json_with_charset(self) -> None:
        """JSON with charset extracts base type."""
        result = extract_json_type("application/json; charset=utf-8")
        assert result == "application/json"

    def test_json_case_insensitive(self) -> None:
        """JSON detection is case insensitive."""
        result = extract_json_type("APPLICATION/JSON")
        assert result == "application/json"

    def test_json_uppercase_with_charset(self) -> None:
        """JSON uppercase with charset works."""
        result = extract_json_type("APPLICATION/JSON; CHARSET=UTF-8")
        assert result == "application/json"

    def test_not_json(self) -> None:
        """Non-JSON returns None."""
        result = extract_json_type("text/html")
        assert result is None

    def test_empty_string(self) -> None:
        """Empty string returns None."""
        result = extract_json_type("")
        assert result is None

    def test_whitespace_only(self) -> None:
        """Whitespace-only returns None."""
        result = extract_json_type("   ")
        assert result is None

    def test_json_in_text_plain(self) -> None:
        """text/plain with json in it still returns None."""
        result = extract_json_type("text/plain; charset=utf-8")
        assert result is None

    def test_vendor_json_type(self) -> None:
        """Vendor-specific JSON types are detected."""
        result = extract_json_type("application/vnd.api+json")
        assert result == "application/vnd.api+json"

    def test_vendor_json_with_charset(self) -> None:
        """Vendor JSON with charset works."""
        result = extract_json_type("application/vnd.api+json; charset=utf-8")
        assert result == "application/vnd.api+json"

    def test_json_with_spaces(self) -> None:
        """JSON with extra spaces works."""
        result = extract_json_type("  application/json  ;  charset=utf-8  ")
        assert result == "application/json"

    def test_multiple_semicolons(self) -> None:
        """Multiple semicolons extract only first part."""
        result = extract_json_type("application/json; a=1; b=2")
        assert result == "application/json"

    def test_complex_charset(self) -> None:
        """Complex charset parameters work."""
        result = extract_json_type(
            "application/json; charset=utf-8; boundary=something",
        )
        assert result == "application/json"

    def test_json_suffix(self) -> None:
        """JSON as suffix is detected."""
        result = extract_json_type("application/ld+json")
        assert result == "application/ld+json"

    def test_json_suffix_with_charset(self) -> None:
        """JSON suffix with charset works."""
        result = extract_json_type("application/ld+json; charset=utf-8")
        assert result == "application/ld+json"

    def test_streaming_json(self) -> None:
        """Streaming JSON type works."""
        result = extract_json_type("application/json-stream")
        assert result == "application/json-stream"