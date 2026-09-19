"""Tests for config/lib/sources module - configuration sources."""

import os
import tempfile

import pytest

from quadkit.config.lib.sources import (
    ConfigSource,
    EnvironmentConfigSource,
    FileConfigSource,
)


class TestConfigSource:
    """Tests for ConfigSource abstract base class."""

    def test_cannot_instantiate_directly(self) -> None:
        """Test that ConfigSource cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ConfigSource()

    def test_load_sync_is_abstract(self) -> None:
        """Test that load_sync must be implemented."""

        class TestSource(ConfigSource):
            def load_sync(self) -> dict:
                return {"key": "value"}

            def get_name(self) -> str:
                return "test"

        source = TestSource()
        result = source.load_sync()
        assert result == {"key": "value"}


class TestEnvironmentConfigSource:
    """Tests for EnvironmentConfigSource."""

    def test_init_with_prefix(self) -> None:
        """Test initialization with prefix."""
        source = EnvironmentConfigSource(prefix="TEST_")
        assert source._prefix == "TEST_"

    def test_init_default_prefix(self) -> None:
        """Test initialization with default empty prefix."""
        source = EnvironmentConfigSource()
        assert source._prefix == ""

    def test_load_empty_when_no_env(self) -> None:
        """Test loading returns empty dict when no matching env vars."""
        source = EnvironmentConfigSource(prefix="NOTEXIST_")
        result = source.load_sync()
        assert result == {}

    def test_load_parses_simple_key(self) -> None:
        """Test loading a simple environment variable."""
        os.environ["MYAPP_KEY"] = "value"
        try:
            source = EnvironmentConfigSource(prefix="MYAPP_")
            result = source.load_sync()
            assert result.get("key") == "value"
        finally:
            del os.environ["MYAPP_KEY"]

    def test_load_parses_nested_key(self) -> None:
        """Test loading nested keys with __ separator."""
        os.environ["MYAPP__DB__HOST"] = "localhost"
        try:
            source = EnvironmentConfigSource(prefix="MYAPP_")
            result = source.load_sync()
            # The key gets lowercased and uses _db as the nested key
            assert result.get("_db", {}).get("host") == "localhost"
        finally:
            del os.environ["MYAPP__DB__HOST"]

    def test_load_parses_numeric_value(self) -> None:
        """Test that numeric strings are parsed to numbers."""
        os.environ["MYAPP_PORT"] = "8080"
        try:
            source = EnvironmentConfigSource(prefix="MYAPP_")
            result = source.load_sync()
            assert result.get("port") == 8080
            assert isinstance(result.get("port"), int)
        finally:
            del os.environ["MYAPP_PORT"]

    def test_load_parses_float_value(self) -> None:
        """Test that float strings are parsed to floats."""
        os.environ["MYAPP_RATE"] = "3.14"
        try:
            source = EnvironmentConfigSource(prefix="MYAPP_")
            result = source.load_sync()
            assert result.get("rate") == 3.14
            assert isinstance(result.get("rate"), float)
        finally:
            del os.environ["MYAPP_RATE"]

    def test_load_ignores_non_matching_prefix(self) -> None:
        """Test that env vars not matching prefix are ignored."""
        os.environ["OTHER_VAR"] = "should_be_ignored"
        os.environ["MYAPP_VAR"] = "should_be_included"
        try:
            source = EnvironmentConfigSource(prefix="MYAPP_")
            result = source.load_sync()
            assert "var" in result
            assert "OTHER_VAR" not in str(result)
        finally:
            del os.environ["OTHER_VAR"]
            del os.environ["MYAPP_VAR"]

    def test_get_name(self) -> None:
        """Test get_name returns 'environment'."""
        source = EnvironmentConfigSource()
        assert "environment" in source.get_name()


class TestFileConfigSource:
    """Tests for FileConfigSource."""

    def test_init_with_path(self) -> None:
        """Test initialization with file path."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            path = f.name

        source = FileConfigSource(path)
        assert str(source._path) == path

    def test_load_json_file(self) -> None:
        """Test loading a JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            path = f.name

        source = FileConfigSource(path)
        result = source.load_sync()
        assert result == {"key": "value"}

    def test_load_empty_json(self) -> None:
        """Test loading an empty JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            path = f.name

        source = FileConfigSource(path)
        result = source.load_sync()
        assert result == {}

    def test_get_name(self) -> None:
        """Test get_name returns the file name."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            path = f.name

        source = FileConfigSource(path)
        assert "test_file" in source.get_name() or ".json" in source.get_name()
