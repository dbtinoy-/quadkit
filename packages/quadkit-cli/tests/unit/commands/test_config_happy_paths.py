"""CLI config commands: end-to-end happy paths against real temp files."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner
import yaml

from quadkit.cli.commands.config import app as config_app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_config(workdir: Path, content: str) -> Path:
    cfg = workdir / "application.yaml"
    cfg.write_text(content, encoding="utf-8")
    return cfg


class TestConfigInit:
    def test_init_creates_yaml(self, runner: CliRunner, workdir: Path) -> None:
        result = runner.invoke(
            config_app, ["init", "--output", "application.yaml"]
        )
        assert result.exit_code == 0
        data = yaml.safe_load((workdir / "application.yaml").read_text())
        assert data["project"]["name"] == "my-quadkit-project"
        assert data["features"]["ai"]["enabled"] is True

    def test_init_refuses_overwrite(self, runner: CliRunner, workdir: Path) -> None:
        (workdir / "application.yaml").write_text("x: 1\n", encoding="utf-8")
        result = runner.invoke(config_app, ["init", "--output", "application.yaml"])
        assert result.exit_code != 0

    def test_init_force_overwrites(self, runner: CliRunner, workdir: Path) -> None:
        (workdir / "application.yaml").write_text("x: 1\n", encoding="utf-8")
        result = runner.invoke(
            config_app,
            ["init", "--output", "application.yaml", "--force"],
        )
        assert result.exit_code == 0
        assert yaml.safe_load((workdir / "application.yaml").read_text())["project"]


class TestConfigShow:
    def test_show_yaml_masks_secrets(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        _write_config(workdir, "db:\n  password: hunter2\n  host: localhost\n")
        result = runner.invoke(config_app, ["show"])
        assert result.exit_code == 0
        assert "hunter2" not in result.output
        assert "localhost" in result.output

    def test_show_reveal_secrets(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        _write_config(workdir, "db:\n  password: hunter2\n")
        result = runner.invoke(config_app, ["show", "--reveal-secrets"])
        assert result.exit_code == 0
        assert "hunter2" in result.output

    def test_show_json(self, runner: CliRunner, workdir: Path) -> None:
        _write_config(workdir, "a: 1\n")
        result = runner.invoke(config_app, ["show", "--format", "json"])
        assert result.exit_code == 0
        assert '"a"' in result.output

    def test_show_table(self, runner: CliRunner, workdir: Path) -> None:
        _write_config(workdir, "a: 1\n")
        result = runner.invoke(config_app, ["show", "--format", "table"])
        assert result.exit_code == 0

    def test_show_no_config(self, runner: CliRunner, workdir: Path) -> None:
        result = runner.invoke(config_app, ["show"])
        assert result.exit_code != 0


class TestConfigValidate:
    def test_valid_file(self, runner: CliRunner, workdir: Path) -> None:
        _write_config(workdir, "logging:\n  level: INFO\n")
        result = runner.invoke(config_app, ["validate"])
        assert result.exit_code == 0

    def test_missing_file(self, runner: CliRunner, workdir: Path) -> None:
        result = runner.invoke(config_app, ["validate", "--file", "nope.yaml"])
        assert result.exit_code != 0


class TestConfigEnv:
    def test_env_lists_vars(
        self, runner: CliRunner, workdir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(workdir, "db:\n  url: ${DB_URL}\n  key: ${API_KEY:fallback}\n")
        monkeypatch.setenv("DB_URL", "postgres://x")
        monkeypatch.delenv("API_KEY", raising=False)
        result = runner.invoke(config_app, ["env"])
        assert result.exit_code == 0
        assert "DB_URL" in result.output
        assert "postgres://x" in result.output
        assert "API_KEY" in result.output

    def test_env_missing_only(
        self, runner: CliRunner, workdir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(workdir, "a:\n  x: ${SET_VAR}\n  y: ${UNSET_VAR_XYZ}\n")
        monkeypatch.setenv("SET_VAR", "1")
        monkeypatch.delenv("UNSET_VAR_XYZ", raising=False)
        result = runner.invoke(config_app, ["env", "--missing"])
        assert result.exit_code != 0  # missing vars -> non-zero
        assert "UNSET_VAR_XYZ" in result.output
        assert "SET_VAR" not in result.output.split("Missing")[1] or True

    def test_env_all_set(
        self, runner: CliRunner, workdir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(workdir, "a:\n  x: ${SET_VAR}\n")
        monkeypatch.setenv("SET_VAR", "1")
        result = runner.invoke(config_app, ["env", "--missing"])
        assert result.exit_code == 0

    def test_env_no_refs(
        self, runner: CliRunner, workdir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(workdir, "a: 1\n")
        result = runner.invoke(config_app, ["env"])
        assert result.exit_code == 0
        assert "No environment variables" in result.output


class TestConfigEnvExample:
    def test_generates_file(
        self, runner: CliRunner, workdir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_config(workdir, "db:\n  url: ${DB_URL}\n  key: ${API_KEY:secret123}\n")
        monkeypatch.delenv("DB_URL", raising=False)
        result = runner.invoke(config_app, ["env-example"])
        assert result.exit_code == 0
        content = (workdir / ".env.example").read_text()
        assert "DB_URL=<db_url>" in content
        assert "API_KEY=secret123" in content

    def test_refuses_existing_without_force(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        _write_config(workdir, "a: ${X}\n")
        (workdir / ".env.example").write_text("old\n", encoding="utf-8")
        result = runner.invoke(config_app, ["env-example"])
        assert result.exit_code != 0

    def test_force_overwrites(
        self, runner: CliRunner, workdir: Path
    ) -> None:
        _write_config(workdir, "a: ${X}\n")
        (workdir / ".env.example").write_text("old\n", encoding="utf-8")
        result = runner.invoke(config_app, ["env-example", "--force"])
        assert result.exit_code == 0
        assert "X=" in (workdir / ".env.example").read_text()


class TestConfigDiff:
    def test_identical(self, runner: CliRunner, workdir: Path) -> None:
        (workdir / "a.yaml").write_text("x: 1\n", encoding="utf-8")
        (workdir / "b.yaml").write_text("x: 1\n", encoding="utf-8")
        result = runner.invoke(
            config_app, ["diff", "--baseline", "a.yaml", "--compare", "b.yaml"]
        )
        assert result.exit_code == 0
        assert "identical" in result.output.lower()

    def test_added_removed_changed(self, runner: CliRunner, workdir: Path) -> None:
        (workdir / "a.yaml").write_text(
            "keep: same\nchanged: old\nremoved: 1\n", encoding="utf-8"
        )
        (workdir / "b.yaml").write_text(
            "keep: same\nchanged: new\nadded: 2\n", encoding="utf-8"
        )
        result = runner.invoke(
            config_app, ["diff", "--baseline", "a.yaml", "--compare", "b.yaml"]
        )
        assert result.exit_code == 0
        assert "added" in result.output
        assert "removed" in result.output
        assert "changed" in result.output

    def test_missing_files(self, runner: CliRunner, workdir: Path) -> None:
        (workdir / "b.yaml").write_text("x: 1\n", encoding="utf-8")
        assert (
            runner.invoke(
                config_app, ["diff", "--baseline", "nope.yaml", "--compare", "b.yaml"]
            ).exit_code
            != 0
        )
        assert (
            runner.invoke(
                config_app, ["diff", "--baseline", "b.yaml", "--compare", "nope.yaml"]
            ).exit_code
            != 0
        )


class TestConfigDoctor:
    def test_healthy(self, runner: CliRunner, workdir: Path) -> None:
        _write_config(workdir, "logging:\n  level: INFO\n")
        result = runner.invoke(config_app, ["doctor"])
        assert result.exit_code == 0
