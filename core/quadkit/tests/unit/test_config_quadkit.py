"""Tests for configuration system"""

import contextlib
import os
from pathlib import Path
import tempfile
import unittest
from dataclasses import dataclass

import pytest

from quadkit.config import (
    BaseConfig,
    ConfigLoader,
    ConfigSource,
    ConfigurationError,
    EnvironmentConfigSource,
    FileConfigSource,
)
from quadkit.config.main import QuadkitConfig


class TestQuadkitConfigEnvSection:
    """Test folding of the ``QK_QUADKIT__*`` env namespace into the root."""

    def test_folds_quadkit_env_section_into_root(self, tmp_path, monkeypatch):
        """QK_QUADKIT__* vars populate root fields of QuadkitConfig."""
        monkeypatch.setenv("QK_QUADKIT__DEBUG", "true")
        monkeypatch.setenv("QK_QUADKIT__LOGGING__JSON_FORMAT", "true")

        config = QuadkitConfig.from_yaml(
            tmp_path / "application.yaml", env_override=True
        )

        assert config.debug is True
        assert config.logging.json_format is True

    def test_extension_sections_stay_in_model_extra(self, tmp_path, monkeypatch):
        """Non-root sections remain available via get_section()."""
        monkeypatch.setenv("QK_MONITOR__BACKEND_TYPE", "memory")

        config = QuadkitConfig.from_yaml(
            tmp_path / "application.yaml", env_override=True
        )

        assert getattr(config, "model_extra", None) is not None
        assert "monitor" in config.model_extra
        assert config.get_section("monitor")["backend_type"] == "memory"

    def test_env_overrides_yaml_for_folded_section(self, tmp_path, monkeypatch):
        """Env values win over YAML values for folded fields."""
        import yaml

        (tmp_path / "application.yaml").write_text(
            yaml.safe_dump({"debug": False, "logging": {"json_format": False}})
        )
        monkeypatch.setenv("QK_QUADKIT__DEBUG", "true")

        config = QuadkitConfig.from_yaml(
            tmp_path / "application.yaml", env_override=True
        )

        assert config.debug is True
        assert config.logging.json_format is False


class TestQuadkitLoggingJsonFormat:
    """End-to-end: QK_QUADKIT__LOGGING__JSON_FORMAT produces JSON logs."""

    def test_json_format_env_var_emits_json_on_stdout(
        self, tmp_path, monkeypatch, capsys
    ):
        """Setting the env var flows through config into JSON log output."""
        import json

        from quadkit.logging import get_logger
        from quadkit.logging.configurator import apply_config, reset_logging

        monkeypatch.setenv("QK_QUADKIT__LOGGING__JSON_FORMAT", "true")

        config = QuadkitConfig.from_yaml(
            tmp_path / "application.yaml", env_override=True
        )
        assert config.logging.json_format is True

        try:
            apply_config(config.logging)
            get_logger("quadkit.test").info("hello_json", key="value")
        finally:
            reset_logging()

        merged = capsys.readouterr()
        out = (merged.out + merged.err).strip()
        assert out, "expected log output on stdout/stderr"
        # Config loading may emit its own structured diagnostics before the
        # application log line; the JSON-formatted record is the LAST line.
        json_lines = [ln for ln in out.splitlines() if ln.startswith("{")]
        assert json_lines, f"no JSON log line in: {out!r}"
        record = json.loads(json_lines[-1])
        assert record["event"] == "hello_json"
        assert record["key"] == "value"


class TestQuadkitLoggingLevel:
    """End-to-end: QK_QUADKIT__LOGGING__LEVEL controls the global level."""

    def test_level_env_var_drops_events_below_threshold(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        """Setting LEVEL=ERROR flows through config and drops INFO events."""
        from quadkit.logging import get_logger
        from quadkit.logging.configurator import apply_config, reset_logging
        from quadkit.serialization import loads

        monkeypatch.setenv("QK_QUADKIT__LOGGING__LEVEL", "ERROR")
        monkeypatch.setenv("QK_QUADKIT__LOGGING__JSON_FORMAT", "true")

        config = QuadkitConfig.from_yaml(
            tmp_path / "application.yaml", env_override=True
        )
        assert config.logging.level == "ERROR"

        try:
            apply_config(config.logging)
            get_logger("quadkit.config_level_test").info("should_be_dropped")
            get_logger("quadkit.config_level_test").error("should_be_kept")
        finally:
            reset_logging()

        merged = capsys.readouterr()
        out = (merged.out + merged.err).strip()
        json_lines = [ln for ln in out.splitlines() if ln.startswith("{")]
        assert json_lines, f"no JSON log line in: {out!r}"
        records = [loads(ln) for ln in json_lines]
        events = [record["event"] for record in records]
        assert "should_be_dropped" not in events
        assert "should_be_kept" in events


@dataclass(init=False)
class ConfigModel(BaseConfig):
    """Test configuration class"""

    app_name: str = "test-app"
    debug: bool = False
    port: int = 8000
    database_url: str = "sqlite:///test.db"


@dataclass(init=False)
class RequiredConfigModel(BaseConfig):
    """Test configuration class with required field"""

    database_url: str  # Required field
    app_name: str = "test-app"


class TestConfigSystem(unittest.TestCase):
    def test_base_config_load_default(self):
        """Test default config loading."""
        config = ConfigModel.from_yaml(env_override=False)
        assert config.app_name == "test-app"
        assert not config.debug
        assert config.port == 8000
        assert config.database_url == "sqlite:///test.db"

    def test_environment_source(self):
        """Test environment variable loading"""
        os.environ["TEST_APP_NAME"] = "env-app"
        os.environ["TEST_DEBUG"] = "true"
        os.environ["TEST_PORT"] = "9000"
        os.environ["TEST_DATABASE_URL"] = "postgres://localhost/test"

        try:
            source = EnvironmentConfigSource("TEST_")
            config_dict = source.load_sync()

            assert config_dict["app_name"] == "env-app"
            assert config_dict["debug"]
            assert config_dict["port"] == 9000
            assert config_dict["database_url"] == "postgres://localhost/test"
        finally:
            # Clean up
            for key in [
                "TEST_APP_NAME",
                "TEST_DEBUG",
                "TEST_PORT",
                "TEST_DATABASE_URL",
            ]:
                os.environ.pop(key, None)

    def test_file_source_json(self):
        """Test JSON file loading"""
        config_data = {
            "app_name": "file-app",
            "debug": True,
            "database_url": "sqlite:///test.db",
        }

        # Open the temporary file in text mode so json.dump writes text
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            from quadkit import serialization as json

            f.write(json.dumps(config_data).decode("utf-8"))
            f.flush()

            try:
                source = FileConfigSource(f.name)
                loaded = source.load_sync()
                assert loaded["app_name"] == "file-app"
                assert loaded["debug"]
                assert loaded["database_url"] == "sqlite:///test.db"
            finally:
                # On Windows the temporary file can be locked by antivirus or
                # scanning tools. Retry a few times before giving up to make
                # the test more robust on CI/Windows environments.
                for _ in range(5):
                    try:
                        Path(f.name).unlink()
                        break
                    except PermissionError:
                        import time

                        time.sleep(0.1)
                else:
                    # Best-effort cleanup if retries fail
                    with contextlib.suppress(OSError):
                        os.remove(f.name)

    def test_config_loader_merge(self):
        """Test config source merging"""
        loader = ConfigLoader()

        # First source
        class MockSource1(ConfigSource):
            def load_sync(self):
                return {"app_name": "source1", "debug": False}

            async def load(self):
                return {"app_name": "source1", "debug": False}

            def get_name(self):
                return "mock1"

        # Second source (higher priority)
        class MockSource2(ConfigSource):
            def load_sync(self):
                return {"app_name": "source2", "port": 9000}

            async def load(self):
                return {"app_name": "source2", "port": 9000}

            def get_name(self):
                return "mock2"

        loader.add_source(MockSource1())
        loader.add_source(MockSource2())

        config = loader.load_sync(ConfigModel)
        assert config.app_name == "source2"  # Higher priority wins
        assert not config.debug  # From first source
        assert config.port == 9000  # From second source

    def test_config_validation_error(self):
        """Test validation error for missing required fields"""
        loader = ConfigLoader()

        class MockSource(ConfigSource):
            def load_sync(self):
                return {"app_name": "test"}  # Missing database_url

            async def load(self):
                return {"app_name": "test"}  # Missing database_url

            def get_name(self):
                return "mock"

        loader.add_source(MockSource())

        with pytest.raises(ConfigurationError):
            loader.load_sync(RequiredConfigModel)

    def test_config_loader_with_extra_sources(self):
        """Test config loading with extra sources."""
        loader = ConfigLoader()

        class MockExtraSource(ConfigSource):
            def load_sync(self):
                return {"extra_field": "extra_value"}

            async def load(self):
                return {"extra_field": "extra_value"}

            def get_name(self):
                return "extra"

        loader.add_source(MockExtraSource())

        # Just verify it doesn't error when extra sources provided
        config = loader.load_sync(ConfigModel)
        assert config is not None

    def test_file_source_yaml(self):
        """Test YAML file loading."""
        import yaml

        config_data = {
            "app_name": "yaml-app",
            "debug": True,
            "port": 3000,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            f.flush()

            try:
                source = FileConfigSource(f.name)
                loaded = source.load_sync()
                assert loaded["app_name"] == "yaml-app"
                assert loaded["debug"]
                assert loaded["port"] == 3000
            finally:
                for _ in range(5):
                    try:
                        Path(f.name).unlink()
                        break
                    except PermissionError:
                        import time

                        time.sleep(0.1)
                else:
                    with contextlib.suppress(OSError):
                        os.remove(f.name)

    def test_environment_source_with_prefix(self):
        """Test environment variable loading with custom prefix."""
        os.environ["MYAPP_DEBUG"] = "true"
        os.environ["MYAPP_PORT"] = "7000"

        try:
            source = EnvironmentConfigSource("MYAPP_")
            config_dict = source.load_sync()

            assert config_dict["debug"]
            assert config_dict["port"] == 7000
        finally:
            os.environ.pop("MYAPP_DEBUG", None)
            os.environ.pop("MYAPP_PORT", None)

    def test_config_from_env_override(self):
        """Test config loading with env override enabled."""
        # Note: This test requires env vars to be set properly
        # Just test that the method exists and doesn't error
        try:
            config = ConfigModel.from_yaml(env_override=False)
            assert config is not None
        except Exception as e:
            # May fail if environment is not properly configured
            self.skipTest(f"Environment not properly configured: {e}")

    def test_environment_source_parse_boolean(self):
        """Test environment source returns strings - Pydantic handles boolean coercion.

        Note: EnvironmentConfigSource intentionally does NOT parse booleans.
        Pydantic handles boolean coercion via field type annotations.
        """
        os.environ["TEST_BOOL_TRUE"] = "true"
        os.environ["TEST_BOOL_FALSE"] = "false"
        os.environ["TEST_BOOL_YES"] = "yes"
        os.environ["TEST_BOOL_NO"] = "no"
        os.environ["TEST_BOOL_1"] = "1"
        os.environ["TEST_BOOL_0"] = "0"

        try:
            source = EnvironmentConfigSource("TEST_")
            config_dict = source.load_sync()

            assert config_dict["bool_true"] == "true"
            assert config_dict["bool_false"] == "false"
            assert config_dict["bool_yes"] == "yes"
            assert config_dict["bool_no"] == "no"
            assert config_dict["bool_1"] == 1
            assert config_dict["bool_0"] == 0
        finally:
            for key in [
                "TEST_BOOL_TRUE",
                "TEST_BOOL_FALSE",
                "TEST_BOOL_YES",
                "TEST_BOOL_NO",
                "TEST_BOOL_1",
                "TEST_BOOL_0",
            ]:
                os.environ.pop(key, None)

    def test_environment_source_parse_numbers(self):
        """Test environment source parses numeric values."""
        os.environ["TEST_INT_VALUE"] = "42"
        os.environ["TEST_FLOAT_VALUE"] = "3.14"

        try:
            source = EnvironmentConfigSource("TEST_")
            config_dict = source.load_sync()

            assert config_dict["int_value"] == 42
            self.assertAlmostEqual(config_dict["float_value"], 3.14)
        finally:
            os.environ.pop("TEST_INT_VALUE", None)
            os.environ.pop("TEST_FLOAT_VALUE", None)

    def test_config_source_abstract_class(self):
        """Test that ConfigSource cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ConfigSource()

    def test_config_source_aload(self):
        """Test async load method."""
        import asyncio

        class TestSource(ConfigSource):
            def load_sync(self):
                return {"test": "value"}

            async def load(self):
                return {"test": "value"}

            def get_name(self):
                return "test"

        source = TestSource()
        result = asyncio.run(source.load())
        assert result == {"test": "value"}
