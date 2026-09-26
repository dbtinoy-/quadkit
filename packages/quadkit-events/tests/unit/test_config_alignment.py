"""Tests verifying events config constants and model_config alignment."""
from __future__ import annotations

import pytest
from quadkit.events.constants import ENV_PREFIX, ENV_NESTED_DELIMITER


class TestEventsConfigConstants:
    def test_env_prefix_exists(self) -> None:
        assert ENV_PREFIX == "QK_EVENTS__"

    def test_env_nested_delimiter_exists(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"

    def test_config_model_config_uses_constants(self) -> None:
        from quadkit.events.config import EventsConfig
        mc = dict(EventsConfig.model_config)
        assert mc.get("env_prefix") == ENV_PREFIX
        assert mc.get("env_nested_delimiter") == ENV_NESTED_DELIMITER

    def test_env_prefix_in_all(self) -> None:
        import quadkit.events.constants as c
        assert "ENV_PREFIX" in c.__all__

    def test_env_nested_delimiter_in_all(self) -> None:
        import quadkit.events.constants as c
        assert "ENV_NESTED_DELIMITER" in c.__all__
