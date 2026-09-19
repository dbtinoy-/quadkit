"""Tests for quadkit.constants module - package-level constants."""

from __future__ import annotations

import pytest

from quadkit import constants


class TestVersion:
    """Test version metadata."""

    def test_version_is_string(self) -> None:
        """__version__ should be a string."""
        assert isinstance(constants.__version__, str)

    def test_version_format(self) -> None:
        """__version__ should follow semantic versioning format."""
        version = constants.__version__
        parts = version.split(".")
        assert len(parts) >= 3, f"Version '{version}' should have at least 3 parts"
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' should be numeric"


class TestPythonVersion:
    """Test Python version requirements."""

    def test_min_python_version_is_tuple(self) -> None:
        """MIN_PYTHON_VERSION should be a tuple of two ints."""
        assert isinstance(constants.MIN_PYTHON_VERSION, tuple)
        assert len(constants.MIN_PYTHON_VERSION) == 2
        major, minor = constants.MIN_PYTHON_VERSION
        assert isinstance(major, int)
        assert isinstance(minor, int)

    def test_min_python_version_value(self) -> None:
        """MIN_PYTHON_VERSION should be (3, 11)."""
        assert constants.MIN_PYTHON_VERSION == (3, 11)


class TestExports:
    """Test that constants are properly exported."""

    def test_all_contains_min_python_version(self) -> None:
        """MIN_PYTHON_VERSION should be in __all__."""
        assert "MIN_PYTHON_VERSION" in constants.__all__

    def test_all_contains_version(self) -> None:
        """__version__ should be in __all__."""
        assert "__version__" in constants.__all__