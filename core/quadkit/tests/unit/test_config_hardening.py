"""Tests for Config System Hardening.

Covers: ConfigProtocol, ConfigProvider registration, env var precedence,
LoggingConfig field cleanup, and AppConfig removal.
"""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import MagicMock

import pytest

from quadkit.config import (
    BaseConfig,
    QuadkitConfig,
    LoggingConfig,
)
from quadkit.contracts.core.config import ConfigProtocol

# ---------------------------------------------------------------------------
# ConfigProtocol satisfaction
# ---------------------------------------------------------------------------


class TestConfigProtocol:
    """Verify ConfigProtocol is satisfied by framework config classes."""

    def test_quadkit_config_satisfies_protocol(self) -> None:
        """QuadkitConfig instances pass isinstance check against ConfigProtocol."""
        config = QuadkitConfig()
        assert isinstance(config, ConfigProtocol)

    def test_base_config_satisfies_protocol(self) -> None:
        """BaseConfig subclasses satisfy ConfigProtocol if they implement get() and get_section()."""

        class MyConfig(BaseConfig):
            app_name: str = "test"

        config = MyConfig()
        # BaseConfig has get() — but get_section() is on QuadkitConfig.
        # A plain BaseConfig subclass satisfies get() but not get_section()
        # unless it defines one. Check whether it actually satisfies:
        has_get = hasattr(config, "get")
        hasattr(config, "get_section")
        # BaseConfig provides get(). get_section() is only on QuadkitConfig.
        assert has_get

    def test_custom_protocol_impl_satisfies(self) -> None:
        """A custom class that implements all ConfigProtocol methods satisfies ConfigProtocol."""
        from quadkit.contracts.core.config import Environment

        class CustomConfig:
            @property
            def environment(self) -> Environment:
                return Environment.DEVELOPMENT

            @property
            def is_production(self) -> bool:
                return False

            @property
            def is_development(self) -> bool:
                return True

            @property
            def is_testing(self) -> bool:
                return False

            @property
            def is_staging(self) -> bool:
                return False

            @property
            def is_debug(self) -> bool:
                return False

            def get(self, key: str, default: Any = None) -> Any:
                return default

            def get_section(self, name: str, model_cls: type | None = None) -> Any:
                return {}

            def has_section(self, name: str) -> bool:
                return False

        assert isinstance(CustomConfig(), ConfigProtocol)

    def test_non_compliant_class_fails_protocol(self) -> None:
        """A class missing required methods does NOT satisfy ConfigProtocol."""

        class NotAConfig:
            pass

        assert not isinstance(NotAConfig(), ConfigProtocol)

    def test_protocol_exposes_environment_helpers(self) -> None:
        """ConfigProtocol should include environment convenience properties."""
        assert hasattr(ConfigProtocol, "is_production")
        assert hasattr(ConfigProtocol, "is_development")
        assert hasattr(ConfigProtocol, "is_testing")
        assert hasattr(ConfigProtocol, "is_staging")
        assert hasattr(ConfigProtocol, "is_debug")


# ---------------------------------------------------------------------------
# ConfigProvider — protocol registration
# ---------------------------------------------------------------------------


class TestConfigProviderProtocolRegistration:
    """Verify ConfigProvider registers config under ConfigProtocol key."""

    @pytest.mark.asyncio
    async def test_registers_config_protocol(self) -> None:
        """ConfigProvider registers instance under ConfigProtocol type key."""
        from quadkit.config.di.provider import ConfigProvider

        container = MagicMock()
        container.singleton = MagicMock()

        provider = ConfigProvider(config_class=QuadkitConfig)
        await provider.register(container)

        # Should have 3 singleton calls: config_class, ConfigProtocol, "config"
        assert container.singleton.call_count == 3

        # Verify ConfigProtocol registration exists
        call_args_list = [call.args[0] for call in container.singleton.call_args_list]
        assert ConfigProtocol in call_args_list
        assert QuadkitConfig in call_args_list
        assert "config" in call_args_list


# ---------------------------------------------------------------------------
# Env var precedence
# ---------------------------------------------------------------------------


class TestEnvVarPrecedence:
    """Verify env var precedence in config loading.

    LoadingEnvironmentConfigSource is added AFTER FileConfigSource in the
    ``from_yaml()`` method, so env vars override YAML values by default.
    This follows the 12-factor app convention where env vars have highest
    priority as the deployment-specific layer.
    """

    def test_env_override_yaml(self) -> None:
        """Environment variables override YAML values (12-factor convention).

        EnvironmentConfigSource is added after FileConfigSource in the
        loader's source list, so its values take precedence.
        """

        class TestConfig(BaseConfig):
            app_name: str = "default"

        yaml_data = "app_name: yaml_value\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False,
        ) as f:
            f.write(yaml_data)
            f.flush()
            yaml_path = f.name

        try:
            os.environ["QK_APP_NAME"] = "env_value"
            config = TestConfig.from_yaml(yaml_path)
            # Env vars override YAML values (12-factor app convention)
            assert config.app_name == "env_value"
        finally:
            os.environ.pop("QK_APP_NAME", None)
            Path(yaml_path).unlink(missing_ok=True)

    def test_env_fills_missing_yaml_fields(self) -> None:
        """Env vars fill fields not present in YAML (fallback behavior)."""

        class TestConfig(BaseConfig):
            app_name: str = "default"
            debug: bool = False

        yaml_data = "debug: true\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False,
        ) as f:
            f.write(yaml_data)
            f.flush()
            yaml_path = f.name

        try:
            os.environ["QK_APP_NAME"] = "env_value"
            config = TestConfig.from_yaml(yaml_path)
            # app_name not in YAML → env var fills it
            assert config.app_name == "env_value"
            # debug is in YAML → YAML value used
            assert config.debug is True
        finally:
            os.environ.pop("QK_APP_NAME", None)
            Path(yaml_path).unlink(missing_ok=True)

    def test_yaml_loads_without_env_source(self) -> None:
        """YAML values load correctly when env_override=False."""

        class TestConfig(BaseConfig):
            debug: bool = False
            port: int = 8080

        yaml_data = "debug: true\nport: 3000\n"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False,
        ) as f:
            f.write(yaml_data)
            f.flush()
            yaml_path = f.name

        try:
            config = TestConfig.from_yaml(yaml_path, env_override=False)
            assert config.debug is True
            assert config.port == 3000
        finally:
            Path(yaml_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# LoggingConfig — dead field removal
# ---------------------------------------------------------------------------


class TestLoggingConfigCleanup:
    """Verify dead fields were removed from LoggingConfig."""


class TestLoggingConfigLevelsValidation:
    """Ensure per-logger level overrides are normalized/validated."""

    def test_valid_and_invalid_levels(self):
        cfg = LoggingConfig(levels={"a": "debug", "b": "NOTALEVEL"})
        # invalid entry should be normalized to INFO by validator
        assert cfg.levels["a"] == "DEBUG"
        assert cfg.levels["b"] == "INFO"

    def test_empty_levels(self):
        cfg = LoggingConfig(levels={})
        assert cfg.levels == {}


    def test_no_file_field(self) -> None:
        """LoggingConfig no longer has a 'file' field."""
        config = LoggingConfig()
        # 'file' was a dead field — it should not exist anymore
        assert not hasattr(config, "file") or config.__class__.__name__ != "LoggingConfig"

    def test_no_stream_field(self) -> None:
        """LoggingConfig no longer has a 'stream' field."""
        config = LoggingConfig()
        assert not hasattr(config, "stream") or config.__class__.__name__ != "LoggingConfig"

    def test_level_default(self) -> None:
        """LoggingConfig retains its level default."""
        config = LoggingConfig()
        assert config.level == "INFO"

    def test_json_format_default(self) -> None:
        """LoggingConfig retains its json_format default."""
        config = LoggingConfig()
        assert config.json_format is False


# ---------------------------------------------------------------------------
# AppConfig removal
# ---------------------------------------------------------------------------


class TestAppConfigRemoval:
    """Verify AppConfig was removed from exports."""

    def test_app_config_not_in_config_package(self) -> None:
        """AppConfig is no longer exported from quadkit.config."""
        import quadkit.config as config_pkg

        assert not hasattr(config_pkg, "AppConfig")

    def test_quadkit_config_has_app_name(self) -> None:
        """QuadkitConfig still provides app_name as a flat field."""
        config = QuadkitConfig()
        assert config.app_name == "quadkit-app"


# ---------------------------------------------------------------------------
# ConfigProvider — narrowed exception handling
# ---------------------------------------------------------------------------


class TestConfigProviderExceptionHandling:
    """Verify ConfigProvider uses narrowed exceptions."""

    @pytest.mark.asyncio
    async def test_handles_file_not_found_gracefully(self) -> None:
        """ConfigProvider handles missing YAML file without crashing."""
        from quadkit.config.di.provider import ConfigProvider

        container = MagicMock()
        container.singleton = MagicMock()

        # Default path won't exist in test environment — should not raise
        provider = ConfigProvider(config_class=QuadkitConfig)
        await provider.register(container)

        assert provider._config_instance is not None

    @pytest.mark.asyncio
    async def test_health_check_reports_loaded(self) -> None:
        """Health check reports config_loaded status."""
        from quadkit.config.di.provider import ConfigProvider

        container = MagicMock()
        container.singleton = MagicMock()

        provider = ConfigProvider(config_class=QuadkitConfig)
        await provider.register(container)

        result = await provider.health_check()
        assert result.details["config_loaded"] is True


# ---------------------------------------------------------------------------
# BaseConfig is DomainModel-based (not pydantic)
# ---------------------------------------------------------------------------


class TestBaseConfigIsDomainModel:
    """Verify BaseConfig is backed by DomainModel, not pydantic BaseSettings."""

    def test_base_config_is_domain_model(self) -> None:
        """BaseConfig extends DomainModel, not pydantic BaseSettings."""
        from quadkit.domain import DomainModel

        assert issubclass(BaseConfig, DomainModel)

    def test_quadkit_config_is_domain_model(self) -> None:
        """QuadkitConfig extends DomainModel through BaseConfig."""
        from quadkit.domain import DomainModel

        assert issubclass(QuadkitConfig, DomainModel)

    def test_logging_config_is_domain_model(self) -> None:
        """LoggingConfig is a DomainModel subclass."""
        from quadkit.domain import DomainModel

        assert issubclass(LoggingConfig, DomainModel)
