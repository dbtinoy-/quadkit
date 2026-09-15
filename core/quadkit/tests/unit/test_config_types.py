"""Tests for config types."""

import pytest

from quadkit.config.types import ConfigSourceType


class TestConfigSourceType:
    """Tests for ConfigSourceType enum."""

    def test_config_source_type_values(self) -> None:
        """Test ConfigSourceType enum values."""
        assert ConfigSourceType.ENVIRONMENT.value == "environment"
        assert ConfigSourceType.FILE.value == "file"
        assert ConfigSourceType.CLI.value == "cli"
        assert ConfigSourceType.DIRECTORY.value == "directory"
        assert ConfigSourceType.MEMORY.value == "memory"

    def test_config_source_type_members(self) -> None:
        """Test ConfigSourceType has expected members."""
        members = list(ConfigSourceType)
        assert len(members) == 5
