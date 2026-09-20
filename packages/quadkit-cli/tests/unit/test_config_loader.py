"""Tests for config discovery and loading."""

import os
from pathlib import Path

import pytest

from quadkit.cli.lib import find_config, load_config_yaml
from quadkit.cli.exceptions import ConfigNotFoundError


class TestFindConfig:
    def test_finds_config_in_cwd(self, tmp_path):
        config_file = tmp_path / "application.yaml"
        config_file.write_text("project:\n  name: test\n")
        result = find_config(start_dir=tmp_path)
        assert result == config_file

    def test_finds_config_in_parent(self, tmp_path):
        config_file = tmp_path / "application.yaml"
        config_file.write_text("project:\n  name: test\n")
        child = tmp_path / "src" / "app"
        child.mkdir(parents=True)
        result = find_config(start_dir=child)
        assert result == config_file

    def test_finds_yml_extension(self, tmp_path):
        config_file = tmp_path / "application.yml"
        config_file.write_text("project:\n  name: test\n")
        result = find_config(start_dir=tmp_path)
        assert result == config_file

    def test_prefers_yaml_over_yml(self, tmp_path):
        (tmp_path / "application.yaml").write_text("yaml version")
        (tmp_path / "application.yml").write_text("yml version")
        result = find_config(start_dir=tmp_path)
        assert result.name == "application.yaml"

    def test_raises_when_not_found(self, tmp_path):
        with pytest.raises(ConfigNotFoundError):
            find_config(start_dir=tmp_path)

    def test_respects_explicit_path(self, tmp_path):
        config_file = tmp_path / "custom" / "config.yaml"
        config_file.parent.mkdir()
        config_file.write_text("project:\n  name: test\n")
        result = find_config(explicit_path=config_file)
        assert result == config_file

    def test_explicit_path_not_found(self, tmp_path):
        with pytest.raises(ConfigNotFoundError):
            find_config(explicit_path=tmp_path / "nope.yaml")

    def test_env_var_override(self, tmp_path, monkeypatch):
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text("project:\n  name: from-env\n")
        monkeypatch.setenv("QK_CONFIG", str(config_file))
        result = find_config(start_dir=tmp_path)
        assert result == config_file


class TestLoadConfigYaml:
    def test_load_valid_yaml(self, tmp_path):
        config_file = tmp_path / "application.yaml"
        config_file.write_text("project:\n  name: myapp\n  version: '1.0'\n")
        data = load_config_yaml(config_file)
        assert data["project"]["name"] == "myapp"

    def test_load_empty_yaml(self, tmp_path):
        config_file = tmp_path / "application.yaml"
        config_file.write_text("")
        data = load_config_yaml(config_file)
        assert data == {}

    def test_load_invalid_yaml(self, tmp_path):
        config_file = tmp_path / "application.yaml"
        config_file.write_text("{{invalid yaml::")
        with pytest.raises(Exception):
            load_config_yaml(config_file)

    def test_env_var_interpolation(self, tmp_path, monkeypatch):
        monkeypatch.setenv("DB_HOST", "localhost")
        monkeypatch.setenv("DB_PORT", "5432")
        config_file = tmp_path / "application.yaml"
        config_file.write_text("database:\n  host: ${DB_HOST}\n  port: ${DB_PORT}\n")
        data = load_config_yaml(config_file)
        assert data["database"]["host"] == "localhost"
        assert data["database"]["port"] == 5432

    def test_env_var_with_default(self, tmp_path):
        config_file = tmp_path / "application.yaml"
        config_file.write_text("database:\n  host: ${DB_HOST:127.0.0.1}\n")
        data = load_config_yaml(config_file)
        assert data["database"]["host"] == "127.0.0.1"
