"""Tests for ${VAR} / ${VAR:default} interpolation in config loading.

Covers QK-001: env-var substitution must run before pydantic/dataclass
coercion at every nesting depth — including nested submodels and lists.

Missing vars with no default must raise ConfigurationError at load time,
not produce the literal ${VAR} string.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest

from quadkit.config.base import BaseConfig
from quadkit.config.lib.merge import interpolate_env_vars, interpolate_string
from quadkit.contracts.exceptions import ConfigurationError


# ---------------------------------------------------------------------------
# interpolate_string unit tests
# ---------------------------------------------------------------------------


class TestInterpolateString:
    """Unit tests for the interpolate_string helper."""

    def test_top_level_var_resolved(self) -> None:
        """${VAR} is replaced when VAR is set in the environment."""
        os.environ["QK_TEST_ISTR_VAR"] = "hello"
        try:
            assert interpolate_string("${QK_TEST_ISTR_VAR}") == "hello"
        finally:
            del os.environ["QK_TEST_ISTR_VAR"]

    def test_default_used_when_var_unset(self) -> None:
        """${VAR:default} returns default when VAR is not set."""
        os.environ.pop("QK_TEST_ISTR_MISSING", None)
        assert interpolate_string("${QK_TEST_ISTR_MISSING:fallback}") == "fallback"

    def test_empty_default_produces_empty_string(self) -> None:
        """${VAR:} with explicit empty default produces empty string, not error."""
        os.environ.pop("QK_TEST_ISTR_EMPTY", None)
        assert interpolate_string("${QK_TEST_ISTR_EMPTY:}") == ""

    def test_missing_var_no_default_raises(self) -> None:
        """${VAR} with no default and VAR unset raises ConfigurationError."""
        os.environ.pop("QK_TEST_ISTR_ABSENT", None)
        with pytest.raises(ConfigurationError, match="QK_TEST_ISTR_ABSENT"):
            interpolate_string("${QK_TEST_ISTR_ABSENT}")

    def test_error_message_names_missing_var(self) -> None:
        """The ConfigurationError message includes the missing variable name."""
        os.environ.pop("QK_TEST_ISTR_NAMED", None)
        with pytest.raises(ConfigurationError) as exc_info:
            interpolate_string("${QK_TEST_ISTR_NAMED}")
        assert "QK_TEST_ISTR_NAMED" in str(exc_info.value)

    def test_no_placeholder_passes_through(self) -> None:
        """Plain strings without ${...} are returned unchanged."""
        assert interpolate_string("plain string") == "plain string"

    def test_var_set_overrides_default(self) -> None:
        """When VAR is set, ${VAR:default} uses the env value, not the default."""
        os.environ["QK_TEST_ISTR_PRESENT"] = "env_val"
        try:
            assert interpolate_string("${QK_TEST_ISTR_PRESENT:default_val}") == "env_val"
        finally:
            del os.environ["QK_TEST_ISTR_PRESENT"]

    def test_partial_string_interpolation(self) -> None:
        """Interpolation works when ${VAR} is embedded inside a longer string."""
        os.environ["QK_TEST_ISTR_HOST"] = "localhost"
        os.environ["QK_TEST_ISTR_PORT"] = "5432"
        try:
            result = interpolate_string(
                "postgresql://${QK_TEST_ISTR_HOST}:${QK_TEST_ISTR_PORT}/db"
            )
            assert result == "postgresql://localhost:5432/db"
        finally:
            del os.environ["QK_TEST_ISTR_HOST"]
            del os.environ["QK_TEST_ISTR_PORT"]


# ---------------------------------------------------------------------------
# interpolate_env_vars unit tests
# ---------------------------------------------------------------------------


class TestInterpolateEnvVars:
    """Unit tests for the interpolate_env_vars dict-level helper."""

    def test_top_level_scalar_resolved(self) -> None:
        """${VAR} in a top-level string field is substituted."""
        os.environ["QK_TEST_IEV_SCALAR"] = "top_value"
        try:
            config: dict = {"name": "${QK_TEST_IEV_SCALAR}"}
            interpolate_env_vars(config)
            assert config["name"] == "top_value"
        finally:
            del os.environ["QK_TEST_IEV_SCALAR"]

    def test_nested_dict_field_resolved(self) -> None:
        """${VAR} inside a nested dict value is substituted."""
        os.environ["QK_TEST_IEV_NESTED"] = "nested_value"
        try:
            config: dict = {"outer": {"inner": "${QK_TEST_IEV_NESTED}"}}
            interpolate_env_vars(config)
            assert config["outer"]["inner"] == "nested_value"
        finally:
            del os.environ["QK_TEST_IEV_NESTED"]

    def test_list_of_strings_resolved(self) -> None:
        """${VAR} inside list string items is substituted."""
        os.environ["QK_TEST_IEV_ITEM"] = "list_item"
        try:
            config: dict = {"items": ["${QK_TEST_IEV_ITEM}", "plain"]}
            interpolate_env_vars(config)
            assert config["items"][0] == "list_item"
            assert config["items"][1] == "plain"
        finally:
            del os.environ["QK_TEST_IEV_ITEM"]

    def test_list_of_dicts_resolved(self) -> None:
        """${VAR} inside dicts nested inside lists is substituted."""
        os.environ["QK_TEST_IEV_DICT_ITEM"] = "dict_item_value"
        try:
            config: dict = {"items": [{"key": "${QK_TEST_IEV_DICT_ITEM}"}]}
            interpolate_env_vars(config)
            assert config["items"][0]["key"] == "dict_item_value"
        finally:
            del os.environ["QK_TEST_IEV_DICT_ITEM"]

    def test_missing_var_raises_at_dict_level(self) -> None:
        """Missing var with no default raises ConfigurationError from dict interpolation."""
        os.environ.pop("QK_TEST_IEV_MISSING", None)
        config: dict = {"key": "${QK_TEST_IEV_MISSING}"}
        with pytest.raises(ConfigurationError, match="QK_TEST_IEV_MISSING"):
            interpolate_env_vars(config)

    def test_default_used_at_nested_level(self) -> None:
        """${VAR:default} in nested dict uses default when VAR is unset."""
        os.environ.pop("QK_TEST_IEV_NESTED_DEF", None)
        config: dict = {"outer": {"inner": "${QK_TEST_IEV_NESTED_DEF:fallback}"}}
        interpolate_env_vars(config)
        assert config["outer"]["inner"] == "fallback"


# ---------------------------------------------------------------------------
# End-to-end: from_yaml with nested pydantic/dataclass submodels
# ---------------------------------------------------------------------------


@dataclass(init=False)
class _QuotaConfig(BaseConfig):
    """Minimal nested config model."""

    limit: int = 0
    window_seconds: int = 3600


@dataclass(init=False)
class _AppConfig(BaseConfig):
    """Top-level config with a nested submodel to test nested interpolation."""

    app_name: str = "default"
    quota: _QuotaConfig = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.quota is None:
            self.quota = _QuotaConfig()


class TestEndToEndInterpolation:
    """Full-stack tests: YAML → interpolation → model coercion."""

    def test_top_level_string_var_resolved(self) -> None:
        """Top-level ${VAR} in YAML resolves to the env value."""
        yaml = "app_name: ${QK_TEST_E2E_APP_NAME}\n"
        os.environ["QK_TEST_E2E_APP_NAME"] = "my-app"
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                f.write(yaml)
                path = f.name
            config = _AppConfig.from_yaml(path, env_override=False)
            assert config.app_name == "my-app"
        finally:
            del os.environ["QK_TEST_E2E_APP_NAME"]
            Path(path).unlink(missing_ok=True)

    def test_top_level_default_used_when_var_unset(self) -> None:
        """${VAR:default} in top-level YAML uses the inline default."""
        yaml = "app_name: ${QK_TEST_E2E_MISSING:default-app}\n"
        os.environ.pop("QK_TEST_E2E_MISSING", None)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml)
            path = f.name
        try:
            config = _AppConfig.from_yaml(path, env_override=False)
            assert config.app_name == "default-app"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_nested_dataclass_field_resolved(self) -> None:
        """${VAR} inside a nested dataclass section is substituted before coercion."""
        yaml = "quota:\n  limit: ${QK_TEST_E2E_LIMIT}\n  window_seconds: 3600\n"
        os.environ["QK_TEST_E2E_LIMIT"] = "50"
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                f.write(yaml)
                path = f.name
            # Load the raw quota section directly to verify interpolation
            from quadkit.config.lib.sources import ConfigLoader, FileConfigSource

            loader = ConfigLoader()
            loader.add_source(FileConfigSource(path))
            raw = loader._collect_sync(None)
            assert raw["quota"]["limit"] == "50"
        finally:
            del os.environ["QK_TEST_E2E_LIMIT"]
            Path(path).unlink(missing_ok=True)

    def test_list_of_objects_in_yaml_resolved(self) -> None:
        """${VAR} inside YAML list-of-dicts is substituted at every depth."""
        yaml = (
            "items:\n"
            "  - key: ${QK_TEST_E2E_LIST_ITEM_A}\n"
            "  - key: static\n"
        )
        os.environ["QK_TEST_E2E_LIST_ITEM_A"] = "dynamic_a"
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                f.write(yaml)
                path = f.name
            from quadkit.config.lib.sources import ConfigLoader, FileConfigSource

            loader = ConfigLoader()
            loader.add_source(FileConfigSource(path))
            raw = loader._collect_sync(None)
            assert raw["items"][0]["key"] == "dynamic_a"
            assert raw["items"][1]["key"] == "static"
        finally:
            del os.environ["QK_TEST_E2E_LIST_ITEM_A"]
            Path(path).unlink(missing_ok=True)

    def test_missing_var_no_default_raises_at_load_time(self) -> None:
        """Missing required var in YAML raises ConfigurationError at load time."""
        yaml = "app_name: ${QK_TEST_E2E_ABSENT_VAR}\n"
        os.environ.pop("QK_TEST_E2E_ABSENT_VAR", None)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml)
            path = f.name
        try:
            with pytest.raises(ConfigurationError, match="QK_TEST_E2E_ABSENT_VAR"):
                _AppConfig.from_yaml(path, env_override=False)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_empty_default_var_produces_empty_string(self) -> None:
        """${VAR:} in YAML produces empty string, not an error."""
        yaml = "app_name: ${QK_TEST_E2E_EMPTY_DEF:}\n"
        os.environ.pop("QK_TEST_E2E_EMPTY_DEF", None)
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write(yaml)
            path = f.name
        try:
            config = _AppConfig.from_yaml(path, env_override=False)
            assert config.app_name == ""
        finally:
            Path(path).unlink(missing_ok=True)
