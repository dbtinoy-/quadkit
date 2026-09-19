"""Tests for DI constants."""

import pytest
from quadkit.di.constants import (
    ENV_PREFIX,
    ENV_NESTED_DELIMITER,
    DEFAULT_MAX_RESOLUTION_DEPTH,
    DEFAULT_SCOPE_NAME,
)


class TestDIConstants:
    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_DI__"

    def test_default_max_resolution_depth(self) -> None:
        assert DEFAULT_MAX_RESOLUTION_DEPTH == 50

    def test_default_scope_name(self) -> None:
        assert DEFAULT_SCOPE_NAME == "request"

    def test_env_nested_delimiter(self) -> None:
        """Test nested delimiter constant."""
        assert ENV_NESTED_DELIMITER == "__"
        assert isinstance(ENV_NESTED_DELIMITER, str)
