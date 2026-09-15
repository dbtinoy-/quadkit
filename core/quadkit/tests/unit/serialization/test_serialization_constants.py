"""Tests for serialization constants."""

import pytest

from quadkit.serialization.constants import (
    DEFAULT_ENCODING,
    DEFAULT_ENSURE_ASCII,
    JSON_BACKEND,
)


class TestSerializationConstants:
    """Tests for serialization constants."""

    def test_default_encoding(self) -> None:
        """Test default encoding."""
        assert DEFAULT_ENCODING == "utf-8"
        assert isinstance(DEFAULT_ENCODING, str)

    def test_default_ensure_ascii(self) -> None:
        """Test default ensure ascii setting."""
        assert DEFAULT_ENSURE_ASCII is False
        assert isinstance(DEFAULT_ENSURE_ASCII, bool)

    def test_json_backend(self) -> None:
        """Test JSON backend is set."""
        assert JSON_BACKEND is not None
        assert isinstance(JSON_BACKEND, str)

    def test_constants_exported(self) -> None:
        """Test that all constants are in __all__."""
        from quadkit.serialization.constants import __all__

        assert "DEFAULT_ENCODING" in __all__
        assert "DEFAULT_ENSURE_ASCII" in __all__
        assert "JSON_BACKEND" in __all__
