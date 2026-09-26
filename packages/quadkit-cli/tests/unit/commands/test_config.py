from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from quadkit.cli.commands.config import _dict_diff, _mask_secrets
from quadkit.cli.exceptions import ConfigNotFoundError


class TestMaskSecrets:
    def test_reveal_secrets(self) -> None:
        config = {"password": "secret123", "name": "test"}
        result = _mask_secrets(config, reveal=True)
        assert result["password"] == "secret123"

    def test_mask_password(self) -> None:
        config = {"password": "secret123"}
        result = _mask_secrets(config)
        assert result["password"] == "***"

    def test_mask_secret_key(self) -> None:
        config = {"api_key": "abc123"}
        result = _mask_secrets(config)
        assert result["api_key"] == "***"

    def test_mask_token(self) -> None:
        config = {"token": "xyz"}
        result = _mask_secrets(config)
        assert result["token"] == "***"

    def test_leaves_normal_keys(self) -> None:
        config = {"name": "test", "port": 8080}
        result = _mask_secrets(config)
        assert result["name"] == "test"
        assert result["port"] == 8080

    def test_masks_database_url_password(self) -> None:
        config = {"url": "postgres://user:pass@localhost/db"}
        result = _mask_secrets(config)
        assert "pass" not in result["url"]
        assert "***:***@" in str(result["url"])

    def test_recursive_masking(self) -> None:
        config = {"nested": {"db": {"password": "secret"}}}
        result = _mask_secrets(config)
        assert result["nested"]["db"]["password"] == "***"


class TestDictDiff:
    def test_identical(self) -> None:
        added, removed, changed = _dict_diff({"a": 1}, {"a": 1})
        assert not added and not removed and not changed

    def test_added_key(self) -> None:
        added, removed, changed = _dict_diff({"a": 1}, {"a": 1, "b": 2})
        assert added == {"b": 2}
        assert not removed and not changed

    def test_removed_key(self) -> None:
        added, removed, changed = _dict_diff({"a": 1, "b": 2}, {"a": 1})
        assert removed == {"b": 2}
        assert not added and not changed

    def test_changed_value(self) -> None:
        added, removed, changed = _dict_diff({"a": 1}, {"a": 2})
        assert changed == {"a": (1, 2)}
        assert not added and not removed

    def test_nested_diff(self) -> None:
        added, removed, changed = _dict_diff(
            {"nested": {"a": 1, "b": 2}},
            {"nested": {"a": 1, "c": 3}},
        )
        assert "nested.b" in removed
        assert "nested.c" in added


class TestConfigCommand:
    runner = CliRunner()

    @patch("quadkit.cli.commands.config.asyncio.run")
    def test_show_no_config(self, mock_run: MagicMock) -> None:
        from quadkit.cli.commands.config import app as config_app

        mock_run.side_effect = FileNotFoundError("no config")

        result = self.runner.invoke(config_app, ["show"])
        assert result.exit_code != 0

    def test_init_already_exists(self) -> None:
        from quadkit.cli.commands.config import app as config_app

        with patch("pathlib.Path.exists", return_value=True):
            result = self.runner.invoke(config_app, ["init", "--output", "app.yaml"])
            assert result.exit_code != 0

    @patch("quadkit.cli.commands.config.Path.exists", return_value=False)
    @patch("quadkit.cli.commands.config.save_config_yaml_async", new_callable=MagicMock)
    def test_init_creates_file(
        self, mock_save: MagicMock, mock_exists: MagicMock
    ) -> None:
        from quadkit.cli.commands.config import app as config_app

        mock_save.return_value = None
        with patch("quadkit.cli.commands.config.asyncio.run") as mock_run:
            mock_run.side_effect = lambda coro: None
            result = self.runner.invoke(
                config_app, ["init", "--output", "app.yaml", "--force"]
            )
        assert result.exit_code == 0

    def test_validate_file_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing --file is reported by the command, not by accident.

        No ``Path.exists`` patch: patching it class-wide makes the whole
        process see an empty filesystem, so the assertion could pass for a
        reason other than the one under test. An empty temporary CWD is what
        "the file is missing" actually means, and the message proves which
        branch ran.
        """
        from quadkit.cli.commands.config import app as config_app

        monkeypatch.chdir(tmp_path)
        result = self.runner.invoke(
            config_app, ["validate", "--file", "nonexistent.yaml"]
        )

        assert result.exit_code != 0
        assert "Configuration file not found: nonexistent.yaml" in result.output

    def test_doctor_file_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``doctor`` reads ./application.yaml, so an empty CWD is the case."""
        from quadkit.cli.commands.config import app as config_app

        monkeypatch.chdir(tmp_path)
        result = self.runner.invoke(config_app, ["doctor"])

        assert result.exit_code != 0
        assert "Configuration file not found" in result.output
        assert "quadkit init" in result.output

    @patch(
        "quadkit.cli.commands.config.find_config",
        side_effect=ConfigNotFoundError,
    )
    def test_env_cmd_file_not_found(self, mock_find_config: MagicMock) -> None:
        # `env` resolves the config through find_config(), which raises
        # ConfigNotFoundError -- not Path.exists(). Patching find_config keeps
        # this test independent of the process CWD, which other suites mutate
        # at collection time.
        from quadkit.cli.commands.config import app as config_app

        result = self.runner.invoke(config_app, ["env"])
        assert result.exit_code != 0
        # Assert the command's own handler produced the message, not the
        # generic top-level CliError fallback.
        assert "No application.yaml found" in result.output

    def test_diff_compare_not_found(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The baseline exists on disk; the compare file is the missing one.

        The previous form patched ``Path.exists`` with ``side_effect=[True,
        False]``, i.e. it simulated the two halves with a counter. Writing the
        baseline for real keeps the "exists" half honest and leaves the
        "missing" half to the filesystem.
        """
        from quadkit.cli.commands.config import app as config_app

        monkeypatch.chdir(tmp_path)
        (tmp_path / "a.yaml").write_text("app:\n  name: demo\n")
        result = self.runner.invoke(
            config_app, ["diff", "--baseline", "a.yaml", "--compare", "b.yaml"]
        )

        assert result.exit_code != 0
        assert "Compare file not found: b.yaml" in result.output
