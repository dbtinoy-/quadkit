"""Tests for DI constants."""

from __future__ import annotations

from quadkit.di.constants import (
    ENV_PREFIX,
    ENV_NESTED_DELIMITER,
    DEFAULT_MAX_RESOLUTION_DEPTH,
    DEFAULT_SCOPE_NAME,
)


class TestDIConstants:
    """Tests for DI constants."""

    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_DI__"

    def test_env_nested_delimiter(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"

    def test_default_max_resolution_depth(self) -> None:
        assert DEFAULT_MAX_RESOLUTION_DEPTH == 50

    def test_default_scope_name(self) -> None:
        assert DEFAULT_SCOPE_NAME == "request"