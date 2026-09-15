"""Tests for serialization types."""

import pytest

from quadkit.serialization.types import JSONBackend


class TestJSONBackend:
    """Tests for JSONBackend enum."""

    def test_json_backend_values(self) -> None:
        """Test JSONBackend enum values."""
        assert JSONBackend.ORJSON.value == "orjson"
        assert JSONBackend.STDLIB.value == "stdlib"

    def test_json_backend_members(self) -> None:
        """Test JSONBackend has expected members."""
        members = list(JSONBackend)
        assert len(members) >= 2

    def test_json_backend_from_string(self) -> None:
        """Test creating JSONBackend from string."""
        assert JSONBackend("orjson") == JSONBackend.ORJSON
