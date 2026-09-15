"""Tests for module constants."""

import pytest

from quadkit.di.module.constants import MODULE_METADATA_ATTR


class TestModuleConstants:
    """Tests for module constants."""

    def test_module_metadata_attr(self) -> None:
        """Test module metadata attribute."""
        assert MODULE_METADATA_ATTR == "__quadkit_module__"
        assert isinstance(MODULE_METADATA_ATTR, str)
        assert MODULE_METADATA_ATTR.startswith("__")

    def test_constants_exported(self) -> None:
        """Test that all constants are in __all__."""
        from quadkit.di.module.constants import __all__

        assert "MODULE_METADATA_ATTR" in __all__
