"""Tests for cache config loaders (env, dict, YAML, JSON)."""

from __future__ import annotations

import pytest

from quadkit.cache.config.loaders import EnvironmentConfigLoader
from quadkit.cache.config.top_level import CacheConfig
from quadkit.serialization import dumps as json_dumps


class TestFromEnv:
    def test_prefix_filtered_and_types_coerced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QK_CACHE__NAME", "env-cache")
        monkeypatch.setenv("QK_CACHE__ENABLED", "true")
        monkeypatch.setenv("QK_CACHE__SERVICE__ENABLE_METRICS", "true")
        monkeypatch.setenv("UNRELATED_VAR", "nope")
        cfg = EnvironmentConfigLoader.from_env()
        assert cfg.name == "env-cache"
        assert cfg.service.enable_metrics is True

    def test_indexed_backends_become_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("QK_CACHE__BACKENDS__0__NAME", "b0")
        monkeypatch.setenv("QK_CACHE__BACKENDS__0__TYPE", "memory")
        monkeypatch.setenv("QK_CACHE__BACKENDS__0__DEFAULT", "true")
        monkeypatch.setenv("QK_CACHE__BACKENDS__1__NAME", "b1")
        monkeypatch.setenv("QK_CACHE__BACKENDS__1__TYPE", "memory")
        monkeypatch.setenv("QK_CACHE__BACKENDS__1__DEFAULT", "false")
        cfg = EnvironmentConfigLoader.from_env()
        assert [b.name for b in cfg.backends] == ["b0", "b1"]
        assert cfg.backends[0].default is True
        assert cfg.backends[1].default is False

    def test_custom_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_CACHE__NAME", "prefixed")
        monkeypatch.delenv("QK_CACHE__NAME", raising=False)
        cfg = EnvironmentConfigLoader.from_env(prefix="MY_CACHE__")
        assert cfg.name == "prefixed"

    def test_empty_env_gives_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k in list(__import__("os").environ):
            if k.upper().startswith("QK_CACHE__"):
                monkeypatch.delenv(k, raising=False)
        cfg = EnvironmentConfigLoader.from_env()
        assert cfg.name == "cache"


class TestFromDict:
    def test_passthrough(self) -> None:
        cfg = EnvironmentConfigLoader.from_dict({"name": "d", "enabled": False})
        assert cfg.name == "d"
        assert cfg.enabled is False

    def test_invalid_dict_raises(self) -> None:
        # Two backends, none marked default → "Exactly one backend" error.
        with pytest.raises(ValueError, match="Exactly one backend"):
            EnvironmentConfigLoader.from_dict(
                {
                    "backends": [
                        {"name": "a", "type": "memory"},
                        {"name": "b", "type": "memory"},
                    ]
                }
            )


class TestFromYaml:
    def test_yaml_file(self, tmp_path) -> None:
        path = tmp_path / "cache.yaml"
        path.write_text(
            "name: yaml-cache\nenabled: false\n",
            encoding="utf-8",
        )
        cfg = EnvironmentConfigLoader.from_yaml(str(path))
        assert cfg.name == "yaml-cache"
        assert cfg.enabled is False

    def test_missing_yaml_dep(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:

        path = tmp_path / "cache.yaml"
        path.write_text("name: x\n", encoding="utf-8")

        real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__

        def fake_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("no yaml")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)
        with pytest.raises(ImportError, match="PyYAML"):
            EnvironmentConfigLoader.from_yaml(str(path))


class TestFromJson:
    def test_json_file(self, tmp_path) -> None:
        cfg_dict = {"name": "json-cache", "enabled": True, "debug": True}
        path = tmp_path / "cache.json"
        path.write_text(json_dumps(cfg_dict).decode("utf-8"), encoding="utf-8")
        cfg = EnvironmentConfigLoader.from_json(str(path))
        assert cfg.name == "json-cache"
        assert cfg.debug is True

    def test_json_roundtrip_with_backends(self, tmp_path) -> None:
        cfg_dict = {
            "name": "jb",
            "backends": [
                {"name": "m", "type": "memory", "default": True},
            ],
        }
        path = tmp_path / "cache.json"
        path.write_text(json_dumps(cfg_dict).decode("utf-8"), encoding="utf-8")
        cfg = EnvironmentConfigLoader.from_json(str(path))
        assert isinstance(cfg, CacheConfig)
        assert cfg.get_backend("m") is not None
