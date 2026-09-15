"""Tests for serialization constants."""

import pytest

from quadkit.serialization.constants import (
    DEFAULT_ENCODING,
    DEFAULT_ENSURE_ASCII,
    JSON_BACKEND,
    __version__,
)


class TestSerializationConstants:
    """Tests for serialization constants."""

    def test_default_encoding(self) -> None:
        """Test default encoding."""
        assert DEFAULT_ENCODING == "utf-8"
        assert isinstance(DEFAULT_ENCODING, str)

    def test_default_ensure_ascii(self) -> None:
        """Test default ensure ascii."""
        assert DEFAULT_ENSURE_ASCII is False
        assert isinstance(DEFAULT_ENSURE_ASCII, bool)

    def test_json_backend_is_set(self) -> None:
        """Test JSON backend is defined."""
        assert JSON_BACKEND is not None

    def test_version_is_string(self) -> None:
        """Test that version is a valid string."""
        assert isinstance(__version__, str)
        assert __version__

    def test_constants_exported(self) -> None:
        """Test that all constants are in __all__."""
        from quadkit.serialization.constants import __all__ as constants_all

        assert "DEFAULT_ENCODING" in constants_all
        assert "DEFAULT_ENSURE_ASCII" in constants_all
        assert "JSON_BACKEND" in constants_all