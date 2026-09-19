"""Tests for config/protocols.py — ConfigSourceProtocol."""

from __future__ import annotations

from quadkit.config.protocols import ConfigSourceProtocol
from quadkit.config.types import ConfigSourceType


class TestConfigSourceProtocol:
    """Tests for ConfigSourceProtocol."""

    def test_protocol_exists(self) -> None:
        """ConfigSourceProtocol is importable."""
        from quadkit.config.protocols import ConfigSourceProtocol

        assert ConfigSourceProtocol is not None

    def test_protocol_has_load_method(self) -> None:
        """ConfigSourceProtocol defines load() method."""
        assert hasattr(ConfigSourceProtocol, "load")

    def test_protocol_has_source_type_property(self) -> None:
        """ConfigSourceProtocol defines source_type property."""
        assert hasattr(ConfigSourceProtocol, "source_type")

    def test_implementation_check(self) -> None:
        """Objects implementing the protocol work correctly."""

        class MyConfigSource:
            def __init__(self) -> None:
                self._data = {"key": "value"}

            def load(self) -> dict[str, str]:
                return self._data

            @property
            def source_type(self) -> ConfigSourceType:
                return ConfigSourceType.FILE

        source = MyConfigSource()
        assert source.load() == {"key": "value"}
        assert source.source_type == ConfigSourceType.FILE

    def test_implementation_with_env_source(self) -> None:
        """Implementation with ENVIRONMENT source type."""

        class EnvConfigSource:
            def load(self) -> dict[str, str]:
                return {"DEBUG": "true", "PORT": "8080"}

            @property
            def source_type(self) -> ConfigSourceType:
                return ConfigSourceType.ENVIRONMENT

        source = EnvConfigSource()
        result = source.load()
        assert result["DEBUG"] == "true"
        assert source.source_type == ConfigSourceType.ENVIRONMENT

    def test_implementation_with_cli_source(self) -> None:
        """Implementation with CLI source type."""

        class CliConfigSource:
            def __init__(self, args: dict[str, str]) -> None:
                self._args = args

            def load(self) -> dict[str, str]:
                return self._args

            @property
            def source_type(self) -> ConfigSourceType:
                return ConfigSourceType.CLI

        source = CliConfigSource({"verbose": "true", "port": "3000"})
        assert source.load()["verbose"] == "true"
        assert source.source_type == ConfigSourceType.CLI
