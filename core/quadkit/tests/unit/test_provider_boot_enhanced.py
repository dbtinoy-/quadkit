"""Tests for enhanced provider boot timeout and required flag."""

from __future__ import annotations

from quadkit.di.provider import Provider


class TestProviderBootAttributes:
    """Tests for Provider boot_timeout and required attributes."""

    def test_default_boot_timeout_is_none(self) -> None:
        """Provider.boot_timeout defaults to None."""
        p = Provider(name="test")
        assert p.boot_timeout is None

    def test_default_required_is_true(self) -> None:
        """Provider.required defaults to True."""
        p = Provider(name="test")
        assert p.required is True

    def test_custom_boot_timeout(self) -> None:
        """Provider accepts custom boot_timeout."""
        p = Provider(name="test", boot_timeout=5.0)
        assert p.boot_timeout == 5.0

    def test_custom_required_false(self) -> None:
        """Provider accepts required=False."""
        p = Provider(name="test", required=False)
        assert p.required is False
