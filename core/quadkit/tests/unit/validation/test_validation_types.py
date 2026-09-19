"""Tests for validation types."""

from __future__ import annotations

import pytest


class TestValidationConstants:
    """Tests for validation constants."""

    def test_code_min_length(self) -> None:
        """Test CODE_MIN_LENGTH constant."""
        from quadkit.validation.constants import CODE_MIN_LENGTH

        assert CODE_MIN_LENGTH == "min_length"

    def test_code_max_length(self) -> None:
        """Test CODE_MAX_LENGTH constant."""
        from quadkit.validation.constants import CODE_MAX_LENGTH

        assert CODE_MAX_LENGTH == "max_length"

    def test_constants_exported(self) -> None:
        """Test that all constants are in __all__."""
        from quadkit.validation import constants

        assert "CODE_MIN_LENGTH" in constants.__all__
        assert "CODE_MAX_LENGTH" in constants.__all__