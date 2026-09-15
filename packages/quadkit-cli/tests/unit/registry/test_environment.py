from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quadkit.cli.registry.environment import (
    DevelopmentEnvironment,
    Environment,
    EnvironmentConfig,
    EnvironmentManager,
    EnvironmentRegistry,
    ProductionEnvironment,
    StagingEnvironment,
    TestEnvironment,
)


class TestEnvironmentConfig:
    def test_defaults(self) -> None:
        cfg = EnvironmentConfig(name="test")
        assert cfg.name == "test"
        assert cfg.description == ""
        assert cfg.variables == {}
        assert cfg.debug is False

    def test_custom(self) -> None:
        cfg = EnvironmentConfig(name="prod", database_url="postgres://localhost", debug=False)
        assert cfg.database_url == "postgres://localhost"


class TestAbstractEnvironment:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            Environment()


class TestDevelopmentEnvironment:
    def test_get_config(self) -> None:
        env = DevelopmentEnvironment()
        cfg = env.get_config()
        assert cfg.name == "development"
        assert cfg.debug is True
        assert cfg.log_level == "DEBUG"

    def test_validate(self) -> None:
        env = DevelopmentEnvironment()
        valid, msg = env.validate()
        assert valid is True

    def test_name_and_description(self) -> None:
        assert DevelopmentEnvironment.name == "development"
        assert "development" in DevelopmentEnvironment.description


class TestStagingEnvironment:
    def test_get_config(self) -> None:
        env = StagingEnvironment()
        cfg = env.get_config()
        assert cfg.name == "staging"
        assert cfg.debug is False

    def test_validate_missing_db_url(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ.get", return_value=""):
            env = StagingEnvironment()
            valid, msg = env.validate()
            assert valid is False
            assert "DATABASE_URL" in msg

    def test_validate_success(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ.get", return_value="postgres://localhost/db"):
            env = StagingEnvironment()
            valid, msg = env.validate()
            assert valid is True

    def test_name(self) -> None:
        assert StagingEnvironment.name == "staging"


class TestProductionEnvironment:
    def test_get_config(self) -> None:
        env = ProductionEnvironment()
        cfg = env.get_config()
        assert cfg.name == "production"
        assert cfg.debug is False
        assert cfg.log_level == "WARNING"

    def test_validate_missing_db_url(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ.get", return_value=""):
            env = ProductionEnvironment()
            valid, msg = env.validate()
            assert valid is False
            assert "DATABASE_URL" in msg

    def test_validate_localhost_db(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ.get", side_effect=lambda k, d=None: {
            "DATABASE_URL": "postgres://localhost/db",
            "AUTH_SECRET": "a" * 32,
        }.get(k, d or "")):
            env = ProductionEnvironment()
            valid, msg = env.validate()
            assert valid is False
            assert "localhost" in msg

    def test_validate_short_secret(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ.get", side_effect=lambda k, d=None: {
            "DATABASE_URL": "postgres://remote/db",
            "AUTH_SECRET": "short",
        }.get(k, d or "")):
            env = ProductionEnvironment()
            valid, msg = env.validate()
            assert valid is False

    def test_validate_success(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ.get", side_effect=lambda k, d=None: {
            "DATABASE_URL": "postgres://remote/db",
            "AUTH_SECRET": "a" * 32,
        }.get(k, d or "")):
            env = ProductionEnvironment()
            valid, msg = env.validate()
            assert valid is True

    def test_name(self) -> None:
        assert ProductionEnvironment.name == "production"


class TestTestEnvironment:
    def test_get_config(self) -> None:
        env = TestEnvironment()
        cfg = env.get_config()
        assert cfg.name == "test"
        assert cfg.debug is True

    def test_validate(self) -> None:
        env = TestEnvironment()
        valid, msg = env.validate()
        assert valid is True

    def test_name(self) -> None:
        assert TestEnvironment.name == "test"


class TestEnvironmentRegistry:
    def test_register_and_get(self) -> None:
        registry = EnvironmentRegistry()
        registry.register(DevelopmentEnvironment)
        env = registry.get("development")
        assert env is not None
        assert env.name == "development"

    def test_get_nonexistent(self) -> None:
        registry = EnvironmentRegistry()
        assert registry.get("nonexistent") is None

    def test_get_all(self) -> None:
        registry = EnvironmentRegistry()
        registry.register(DevelopmentEnvironment)
        all_envs = registry.get_all()
        assert "development" in all_envs

    def test_get_choices(self) -> None:
        registry = EnvironmentRegistry.with_defaults()
        choices = registry.get_choices()
        assert "development" in choices

    def test_with_defaults_populates_all_environments(self) -> None:
        registry = EnvironmentRegistry.with_defaults()
        assert registry.get("development") is not None
        assert registry.get("production") is not None

    def test_set_current(self) -> None:
        registry = EnvironmentRegistry.with_defaults()
        with patch("quadkit.cli.registry.environment.os.environ") as mock_env:
            registry.set_current("development")
            mock_env.__setitem__.assert_called_with("QK_ENV", "development")

    def test_set_current_unknown(self) -> None:
        registry = EnvironmentRegistry.with_defaults()
        with pytest.raises(ValueError):
            registry.set_current("nonexistent")

    def test_get_current(self) -> None:
        registry = EnvironmentRegistry.with_defaults()
        with patch("quadkit.cli.registry.environment.os.environ.get", return_value="test"):
            assert registry.get_current() == "test"

    def test_get_current_default(self) -> None:
        registry = EnvironmentRegistry.with_defaults()
        with patch.dict("quadkit.cli.registry.environment.os.environ", {}, clear=True):
            assert registry.get_current() == "development"

    def test_get_current_env(self) -> None:
        registry = EnvironmentRegistry.with_defaults()
        with patch("quadkit.cli.registry.environment.os.environ.get", return_value="development"):
            env = registry.get_current_env()
            assert env is not None
            assert env.name == "development"

class TestEnvironmentManager:
    def test_switch_success(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ"):
            manager = EnvironmentManager()
            result = manager.switch("development")
            assert result is True

    def test_switch_nonexistent(self) -> None:
        manager = EnvironmentManager()
        result = manager.switch("nonexistent")
        assert result is False

    def test_validate_current(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ.get", return_value="development"):
            manager = EnvironmentManager()
            valid, msg = manager.validate_current()
            assert valid is True

    def test_validate_current_no_env(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ.get", return_value="unknown"):
            manager = EnvironmentManager()
            valid, msg = manager.validate_current()
            assert valid is False

    def test_get_config(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ.get", return_value="development"):
            manager = EnvironmentManager()
            cfg = manager.get_config()
            assert cfg is not None
            assert cfg.name == "development"

    def test_get_config_no_env(self) -> None:
        with patch("quadkit.cli.registry.environment.os.environ.get", return_value="unknown"):
            manager = EnvironmentManager()
            cfg = manager.get_config()
            assert cfg is None
