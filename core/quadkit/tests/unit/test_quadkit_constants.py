"""Tests for quadkit package constants."""

from __future__ import annotations

from quadkit.constants import MIN_PYTHON_VERSION, __version__


class TestVersion:
    """Tests for version."""

    def test_version_is_string(self) -> None:
        assert isinstance(__version__, str)

    def test_version_format(self) -> None:
        parts = __version__.split(".")
        assert len(parts) >= 3


class TestMinPythonVersion:
    """Tests for minimum Python version."""

    def test_is_tuple(self) -> None:
        assert isinstance(MIN_PYTHON_VERSION, tuple)

    def test_has_two_parts(self) -> None:
        assert len(MIN_PYTHON_VERSION) == 2

    def test_major_is_3(self) -> None:
        assert MIN_PYTHON_VERSION[0] >= 3

    def test_minor_is_11_or_higher(self) -> None:
        assert MIN_PYTHON_VERSION[1] >= 11

