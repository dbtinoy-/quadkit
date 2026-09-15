"""Config source loaders: env, dotenv, directory, cli, file, loader."""

from __future__ import annotations

from argparse import Namespace
from dataclasses import dataclass
import json  # noqa: TID251 — config loading intentionally uses stdlib json, not quadkit.serialization
import os
from pathlib import Path

import pytest

from quadkit.config.lib.sources import (
    CliConfigSource,
    ConfigLoader,
    ConfigSource,
    DirectoryConfigSource,
    DotEnvSource,
    EnvironmentConfigSource,
    FileConfigSource,
)
from quadkit.contracts.exceptions import ConfigurationError
from quadkit.contracts.exceptions.domain import ValidationError


class _OpenSchema:
    """Schema accepting any kwargs (for merge-order assertions)."""

    def __init__(self, **kwargs: object) -> None:
        self.data = kwargs

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _OpenSchema) and self.data == other.data

    __hash__ = None  # mutable data -> unhashable by design


@dataclass
class _TypedSchema:
    port: int = 8000
    name: str = "default"


class _FailingSchema:
    def __init__(self, **kwargs: object) -> None:
        raise ValidationError("schema rejected config", details=[])


class TestEnvironmentConfigSource:
    def test_prefix_lowercase_nesting_and_coercion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MYAPP_DB__HOST", "localhost")
        monkeypatch.setenv("MYAPP_DB__PORT", "5432")
        monkeypatch.setenv("MYAPP_TIMEOUT", "2.5")
        monkeypatch.setenv("MYAPP_ENABLED", "true")
        monkeypatch.setenv("MYAPP_KEEP", "not-a-number")
        monkeypatch.setenv("OTHER_VAR", "ignored")

        data = EnvironmentConfigSource(prefix="MYAPP_").load_sync()
        assert data == {
            "db": {"host": "localhost", "port": 5432},
            "timeout": 2.5,
            "enabled": "true",  # no bool coercion by design
            "keep": "not-a-number",
        }
        assert "OTHER_VAR" not in data

    def test_empty_prefix_reads_all(self) -> None:
        src = EnvironmentConfigSource()
        assert isinstance(src.load_sync(), dict)
        assert src.get_name() == "environment()"


class TestDotEnvSource:
    def test_populates_env_and_loads(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dotenv = tmp_path / ".env"
        dotenv.write_text(
            "FROM_DOTENV=value1\nSHARED=from-file\n# comment\n\n",
            encoding="utf-8",
        )
        monkeypatch.delenv("SHARED", raising=False)
        monkeypatch.delenv("FROM_DOTENV", raising=False)

        data = DotEnvSource(path=dotenv).load_sync()
        assert data["from_dotenv"] == "value1"
        assert data["shared"] == "from-file"
        assert os.environ["FROM_DOTENV"] == "value1"

    def test_existing_env_not_overridden_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dotenv = tmp_path / ".env"
        dotenv.write_text("SHARED=from-file\n", encoding="utf-8")
        monkeypatch.setenv("SHARED", "from-env")

        data = DotEnvSource(path=dotenv).load_sync()
        assert data["shared"] == "from-env"

    def test_override_flag_wins(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dotenv = tmp_path / ".env"
        dotenv.write_text("SHARED=from-file\n", encoding="utf-8")
        monkeypatch.setenv("SHARED", "from-env")

        data = DotEnvSource(path=dotenv, override=True).load_sync()
        assert data["shared"] == "from-file"

    def test_missing_file_with_prefix_empty(self, tmp_path: Path) -> None:
        src = DotEnvSource(path=tmp_path / "nope.env", prefix="NEVER_SET_PFX_")
        assert src.load_sync() == {}

    def test_prefix_filter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dotenv = tmp_path / ".env"
        dotenv.write_text("PFX_A=1\nOTHER_B=2\n", encoding="utf-8")
        monkeypatch.delenv("PFX_A", raising=False)
        monkeypatch.delenv("OTHER_B", raising=False)

        data = DotEnvSource(path=dotenv, prefix="PFX_").load_sync()
        assert data == {"a": 1}


class TestDirectoryConfigSource:
    def test_files_namespaced_by_stem(self, tmp_path: Path) -> None:
        (tmp_path / "01-base.yaml").write_text("a: 1\n", encoding="utf-8")
        (tmp_path / "02-override.json").write_text(
            json.dumps({"b": 2}), encoding="utf-8"
        )
        (tmp_path / "_private.yaml").write_text("hidden: true\n", encoding="utf-8")
        (tmp_path / ".hidden.json").write_text("{}\n", encoding="utf-8")
        (tmp_path / "notes.txt").write_text("not config\n", encoding="utf-8")

        data = DirectoryConfigSource(directory=tmp_path).load_sync()
        assert data == {"01_base": {"a": 1}, "02_override": {"b": 2}}
        assert "hidden" not in data

    def test_single_key_stem_merge(self, tmp_path: Path) -> None:
        # File whose single top-level key equals its stem merges directly
        (tmp_path / "database.yaml").write_text(
            "database:\n  host: db\n", encoding="utf-8"
        )
        data = DirectoryConfigSource(directory=tmp_path).load_sync()
        assert data == {"database": {"host": "db"}}

    def test_missing_directory_empty(self, tmp_path: Path) -> None:
        assert DirectoryConfigSource(directory=tmp_path / "gone").load_sync() == {}

    def test_bad_file_skipped_not_fatal(self, tmp_path: Path) -> None:
        (tmp_path / "good.yaml").write_text("a: 1\n", encoding="utf-8")
        (tmp_path / "bad.json").write_text("{broken", encoding="utf-8")
        data = DirectoryConfigSource(directory=tmp_path).load_sync()
        assert data == {"good": {"a": 1}}


class TestCliConfigSource:
    def test_config_file_attribute(self, tmp_path: Path) -> None:
        cfg = tmp_path / "cli.json"
        cfg.write_text(json.dumps({"port": 9999}), encoding="utf-8")
        data = CliConfigSource(args=Namespace(config=str(cfg))).load_sync()
        assert data == {"port": 9999}

    def test_env_prefix_attribute(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLIPFX_HOST", "fromenv")
        data = CliConfigSource(args=Namespace(env_prefix="CLIPFX_")).load_sync()
        assert data == {"host": "fromenv"}

    def test_argv_config_flag(self, tmp_path: Path) -> None:
        cfg = tmp_path / "argv.json"
        cfg.write_text(json.dumps({"from": "argv"}), encoding="utf-8")
        argv = ["prog", "--config", str(cfg)]
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr("sys.argv", argv)
        try:
            assert CliConfigSource().load_sync() == {"from": "argv"}
        finally:
            monkeypatch.undo()

    def test_no_args_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.argv", ["prog"])
        assert CliConfigSource().load_sync() == {}

    def test_get_name(self) -> None:
        assert CliConfigSource().get_name() == "cli"


class TestFileConfigSource:
    def test_json_and_yaml(self, tmp_path: Path) -> None:
        jf = tmp_path / "a.json"
        jf.write_text(json.dumps({"x": 1}), encoding="utf-8")
        yf = tmp_path / "b.yaml"
        yf.write_text("y: 2\n", encoding="utf-8")
        assert FileConfigSource(jf).load_sync() == {"x": 1}
        assert FileConfigSource(yf).load_sync() == {"y": 2}

    def test_non_object_json_rejected(self, tmp_path: Path) -> None:
        jf = tmp_path / "arr.json"
        jf.write_text("[1, 2]", encoding="utf-8")
        with pytest.raises(ConfigurationError, match="JSON object"):
            FileConfigSource(jf).load_sync()

    def test_unknown_extension_json_then_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "config.conf"
        f.write_text("z: 3\n", encoding="utf-8")
        assert FileConfigSource(f).load_sync() == {"z": 3}

    def test_missing_file_empty(self, tmp_path: Path) -> None:
        assert FileConfigSource(tmp_path / "nope.json").load_sync() == {}

    def test_oserror_raises_configuration_error(self, tmp_path: Path) -> None:
        d = tmp_path / "adir.json"
        d.mkdir()  # IsADirectoryError is an OSError
        with pytest.raises(ConfigurationError):
            FileConfigSource(d).load_sync()

    async def test_async_load(self, tmp_path: Path) -> None:
        yf = tmp_path / "a.yaml"
        yf.write_text("ok: true\n", encoding="utf-8")
        assert (await FileConfigSource(yf).load()) == {"ok": True}
        assert (await FileConfigSource(tmp_path / "gone.yaml").load()) == {}

    def test_get_name(self, tmp_path: Path) -> None:
        src = FileConfigSource(tmp_path / "x.json")
        assert src.get_name().startswith("file(")
        assert not src.pre_interpolated


class TestConfigSourceBase:
    def test_custom_source(self) -> None:
        class Mine(ConfigSource):
            def load_sync(self) -> dict:
                return {"from": "custom"}

            def get_name(self) -> str:
                return "mine"

        assert Mine().load_sync() == {"from": "custom"}

    async def test_default_async_load_delegates(self) -> None:
        class Mine(ConfigSource):
            def load_sync(self) -> dict:
                return {"a": 1}

            def get_name(self) -> str:
                return "mine"

        assert (await Mine().load()) == {"a": 1}


class TestConfigLoader:
    def test_merge_order_later_source_wins(self, tmp_path: Path) -> None:
        low = tmp_path / "low.yaml"
        low.write_text("name: low\nport: 8000\n", encoding="utf-8")
        high = tmp_path / "high.json"
        high.write_text(json.dumps({"name": "high"}), encoding="utf-8")

        loader = ConfigLoader()
        result = loader.load_sync(
            _OpenSchema,
            sources=[FileConfigSource(low), FileConfigSource(high)],
        )
        assert result.data == {"name": "high", "port": 8000}

    def test_add_source_path(self, tmp_path: Path) -> None:
        f = tmp_path / "a.yaml"
        f.write_text("k: v\n", encoding="utf-8")
        loader = ConfigLoader()
        loader.add_source(FileConfigSource(f))
        assert loader.load_sync(_OpenSchema).data == {"k": "v"}

    def test_interpolation_applied_to_authored_sources(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        f = tmp_path / "a.yaml"
        f.write_text("name: ${APP_NAME}\nfallback: ${NOPE_XYZ:defaulted}\n", encoding="utf-8")
        monkeypatch.setenv("APP_NAME", "interpolated")
        monkeypatch.delenv("NOPE_XYZ", raising=False)

        result = ConfigLoader().load_sync(
            _OpenSchema, sources=[FileConfigSource(f)]
        )
        assert result.data == {"name": "interpolated", "fallback": "defaulted"}

    def test_env_source_not_reinterpolated(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # env values may legitimately contain ${...}-shaped text
        monkeypatch.setenv("KEEPXPS_LITERAL", "${STAY_LITERAL}")
        result = ConfigLoader().load_sync(
            _OpenSchema, sources=[EnvironmentConfigSource(prefix="KEEPXPS_")]
        )
        assert result.data == {"literal": "${STAY_LITERAL}"}

    def test_unresolved_interpolation_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        f = tmp_path / "a.yaml"
        f.write_text("name: ${DOES_NOT_EXIST_XYZ}\n", encoding="utf-8")
        monkeypatch.delenv("DOES_NOT_EXIST_XYZ", raising=False)

        with pytest.raises(ConfigurationError, match="Missing required"):
            ConfigLoader().load_sync(
                _OpenSchema, sources=[FileConfigSource(f)]
            )

    def test_source_failure_skipped_and_logged(self, tmp_path: Path) -> None:
        class Broken(ConfigSource):
            def load_sync(self) -> dict:
                raise RuntimeError("source exploded")

            def get_name(self) -> str:
                return "broken"

        good = tmp_path / "good.yaml"
        good.write_text("alive: true\n", encoding="utf-8")
        result = ConfigLoader().load_sync(
            _OpenSchema, sources=[Broken(), FileConfigSource(good)]
        )
        assert result.data == {"alive": True}

    def test_configuration_error_fails_fast(self) -> None:
        class Fatal(ConfigSource):
            def load_sync(self) -> dict:
                raise ConfigurationError("hard stop")

            def get_name(self) -> str:
                return "fatal"

        with pytest.raises(ConfigurationError, match="hard stop"):
            ConfigLoader().load_sync(_OpenSchema, sources=[Fatal()])

    def test_schema_validation_error_wrapped(self) -> None:
        with pytest.raises(ConfigurationError):
            ConfigLoader().load_sync(
                _FailingSchema,
                sources=[EnvironmentConfigSource(prefix="QUADKIT_TEST_NEVER_SET")],
            )

    async def test_async_load(self, tmp_path: Path) -> None:
        f = tmp_path / "a.yaml"
        f.write_text("a: 1\n", encoding="utf-8")
        result = await ConfigLoader().load(
            _OpenSchema, sources=[FileConfigSource(f)]
        )
        assert result.data == {"a": 1}

    def test_typed_schema(self, tmp_path: Path) -> None:
        f = tmp_path / "a.yaml"
        f.write_text("port: 9090\n", encoding="utf-8")
        result = ConfigLoader().load_sync(_TypedSchema, sources=[FileConfigSource(f)])
        assert isinstance(result, _TypedSchema)
        assert result.port == 9090
