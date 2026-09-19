"""Tests for mapping constants."""

from __future__ import annotations

from quadkit.mapping.constants import (
    ENV_PREFIX,
    ENV_NESTED_DELIMITER,
    MAX_MAPPING_DEPTH,
    MAX_MAPPING_RULES,
)


class TestMappingConstants:
    """Tests for mapping constants."""

    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_MAPPING__"

    def test_env_nested_delimiter(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"

    def test_max_mapping_depth(self) -> None:
        assert MAX_MAPPING_DEPTH == 32

    def test_max_mapping_rules(self) -> None:
        assert MAX_MAPPING_RULES == 1024