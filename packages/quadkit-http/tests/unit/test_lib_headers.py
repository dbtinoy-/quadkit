"""Tests for quadkit.http.lib.headers."""

from __future__ import annotations

import pytest

from quadkit.http.lib.headers import merge_headers, parse_headers


class TestParseHeaders:
    """Tests for parse_headers."""

    def test_lowercase_keys(self) -> None:
        """Keys are lowercased."""
        result = parse_headers({"Content-Type": "application/json"})
        assert result == {"content-type": "application/json"}

    def test_multiple_keys(self) -> None:
        """Multiple keys are all lowercased."""
        result = parse_headers({
            "Content-Type": "application/json",
            "Authorization": "Bearer token",
            "X-Request-ID": "123",
        })
        assert result == {
            "content-type": "application/json",
            "authorization": "Bearer token",
            "x-request-id": "123",
        }

    def test_strips_whitespace(self) -> None:
        """Values have whitespace stripped."""
        result = parse_headers({"Content-Type": "  application/json  "})
        assert result == {"content-type": "application/json"}

    def test_numeric_values_converted_to_string(self) -> None:
        """Numeric values are converted to strings."""
        result = parse_headers({"Content-Length": 100})
        assert result == {"content-length": "100"}

    def test_boolean_values_converted_to_string(self) -> None:
        """Boolean values are converted to strings."""
        result = parse_headers({"X-Debug": True})
        assert result == {"x-debug": "True"}

    def test_empty_dict(self) -> None:
        """Empty dict returns empty dict."""
        result = parse_headers({})
        assert result == {}

    def test_none_value(self) -> None:
        """None value causes string conversion."""
        result = parse_headers({"X-Header": None})
        assert result == {"x-header": "None"}

    def test_preserves_case_in_values(self) -> None:
        """Case inside values is preserved."""
        result = parse_headers({"Accept": "APPLICATION/JSON"})
        assert result == {"accept": "APPLICATION/JSON"}

    def test_already_lowercase_keys(self) -> None:
        """Already lowercase keys work fine."""
        result = parse_headers({"accept": "application/json"})
        assert result == {"accept": "application/json"}

    def test_unicode_values(self) -> None:
        """Unicode values are preserved."""
        result = parse_headers({"X-Name": "日本語"})
        assert result == {"x-name": "日本語"}

    def test_empty_string_value(self) -> None:
        """Empty string values are preserved."""
        result = parse_headers({"X-Empty": ""})
        assert result == {"x-empty": ""}


class TestMergeHeaders:
    """Tests for merge_headers."""

    def test_two_dicts(self) -> None:
        """Two dicts are merged."""
        result = merge_headers(
            {"Content-Type": "application/json"},
            {"Authorization": "Bearer token"},
        )
        assert result == {
            "content-type": "application/json",
            "authorization": "Bearer token",
        }

    def test_later_wins_on_duplicate(self) -> None:
        """Later dict wins on duplicate keys."""
        result = merge_headers(
            {"X-Header": "first"},
            {"X-Header": "second"},
        )
        assert result == {"x-header": "second"}

    def test_three_dicts(self) -> None:
        """Three dicts merge correctly."""
        result = merge_headers(
            {"A": "1"},
            {"B": "2"},
            {"C": "3"},
        )
        assert result == {"a": "1", "b": "2", "c": "3"}

    def test_empty_dicts_ignored(self) -> None:
        """Empty dicts are skipped."""
        result = merge_headers({}, {"A": "1"}, {})
        assert result == {"a": "1"}

    def test_none_dict_skipped(self) -> None:
        """Dicts with None items are skipped."""
        result = merge_headers({"A": "1"}, {"B": None})
        assert result == {"a": "1", "b": "None"}

    def test_normalize_true(self) -> None:
        """normalize=True lowercases keys (default)."""
        result = merge_headers(
            {"Content-Type": "text/html"},
            {"Authorization": "Bearer xxx"},
            normalize=True,
        )
        assert result == {"content-type": "text/html", "authorization": "Bearer xxx"}

    def test_normalize_false(self) -> None:
        """normalize=False preserves case."""
        result = merge_headers(
            {"Content-Type": "text/html"},
            normalize=False,
        )
        assert result == {"Content-Type": "text/html"}

    def test_empty_call(self) -> None:
        """No args returns empty dict."""
        result = merge_headers()
        assert result == {}

    def test_all_empty_dicts(self) -> None:
        """All empty dicts returns empty."""
        result = merge_headers({}, {}, {})
        assert result == {}

    def test_numeric_values(self) -> None:
        """Numeric values in merged dicts are converted."""
        result = merge_headers({"Content-Length": 1024, "X-Count": 5})
        assert result["content-length"] == "1024"
        assert result["x-count"] == "5"

    def test_strips_whitespace(self) -> None:
        """Values are stripped of whitespace."""
        result = merge_headers({"X-Header": "  value  "})
        assert result["x-header"] == "value"

    def test_first_dict_empty(self) -> None:
        """First empty dict is handled."""
        result = merge_headers({}, {"A": "1"})
        assert result == {"a": "1"}

    def test_last_dict_empty(self) -> None:
        """Last empty dict is handled."""
        result = merge_headers({"A": "1"}, {})
        assert result == {"a": "1"}

    def test_many_duplicates_later_wins(self) -> None:
        """Multiple duplicate keys: last wins."""
        result = merge_headers(
            {"A": "1"},
            {"A": "2"},
            {"A": "3"},
            {"A": "4"},
        )
        assert result["a"] == "4"

    def test_strips_values_when_normalizing(self) -> None:
        """Whitespace is stripped when normalizing."""
        result = merge_headers(
            {"Content-Type": "  application/json  "},
        )
        assert result["content-type"] == "application/json"