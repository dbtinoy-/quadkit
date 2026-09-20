"""Tests for ConfigManager.save()."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from quadkit.cli.config import CLIConfig, ConfigManager


class TestConfigManagerSave:
    @pytest.fixture
    def tmp_config(self, tmp_path: Path):
        """Patch ConfigManager.config_path to a temp file."""
        config_file = tmp_path / "application.yaml"
        with patch.object(ConfigManager, "config_path", config_file):
            yield config_file

    def test_save_creates_file(self, tmp_config):
        config = CLIConfig()
        ConfigManager.save(config)
        assert tmp_config.exists()

    def test_save_roundtrip(self, tmp_config):
        config = CLIConfig()
        ConfigManager.save(config)
        loaded = ConfigManager.load()
        assert loaded is not None
        # Check key fields match (exclude model_config which is Pydantic metadata)
        for field in config.model_dump():
            if field != "model_config":
                assert getattr(loaded, field) == getattr(config, field)

    def test_save_creates_parent_directories(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "application.yaml"
        with patch.object(ConfigManager, "config_path", nested):
            ConfigManager.save(CLIConfig())
            assert nested.exists()

    def test_save_handles_corrupt_existing_file(self, tmp_config):
        tmp_config.write_bytes(b"NOT VALID TOML !!!")
        # Should not raise - handles corrupt file by starting fresh
        ConfigManager.save(CLIConfig())
        assert tmp_config.exists()

    def test_save_returns_none(self, tmp_config):
        result = ConfigManager.save(CLIConfig())
        assert result is None
    def test_save_roundtrip_without_tomli_w_omits_none(self, tmp_config, monkeypatch):
        """Fallback TOML writer must not corrupt None into the string 'None'."""
        import builtins

        real_import = builtins.__import__

        def _block_tomli_w(name, *args, **kwargs):
            if name == "tomli_w":
                raise ImportError("tomli_w blocked for test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _block_tomli_w)

        config = CLIConfig()  # env=None by default
        ConfigManager.save(config)
        loaded = ConfigManager.load()
        assert loaded is not None
        for field in config.model_dump():
            if field != "model_config":
                assert getattr(loaded, field) == getattr(config, field)
