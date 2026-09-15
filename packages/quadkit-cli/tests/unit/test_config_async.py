"""Tests for async config loading with aiofiles."""

from __future__ import annotations

from pathlib import Path
import tempfile

import pytest
from typer.testing import CliRunner

from quadkit import serialization as json
from quadkit.cli.commands import config as config_command
from quadkit.cli.lib.config_loader import ConfigLoader, load_config_yaml_async
from quadkit.cli.runtime import CLIContext


class TestConfigLoaderAsync:
    @pytest.mark.asyncio
    async def test_load_config_async(self) -> None:
        """ConfigLoader.load_config() must be async and use aiofiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            data = json.dumps({"version": "1.0", "name": "test"})
            if isinstance(data, bytes):
                config_file.write_bytes(data)
            else:
                config_file.write_text(data)

            loader = ConfigLoader()
            config = await loader.load_config(config_file)

            assert config["version"] == "1.0"
            assert config["name"] == "test"

    @pytest.mark.asyncio
    async def test_save_config_async(self) -> None:
        """ConfigLoader.save_config() must be async and use aiofiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"

            loader = ConfigLoader()
            await loader.save_config(config_file, {"version": "1.0", "name": "test"})

            assert config_file.exists()
            content = config_file.read_text()
            assert "version" in content
            assert "test" in content

    @pytest.mark.asyncio
    async def test_load_config_nonexistent(self) -> None:
        """ConfigLoader.load_config() should raise FileNotFoundError for missing files."""
        loader = ConfigLoader()
        with pytest.raises(FileNotFoundError):
            await loader.load_config(Path("/nonexistent/path/config.json"))

    @pytest.mark.asyncio
    async def test_load_config_invalid_json(self) -> None:
        """ConfigLoader.load_config() should raise error for invalid JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.json"
            config_file.write_text("{invalid json")

            loader = ConfigLoader()
            with pytest.raises(ValueError, match=r".+"):
                await loader.load_config(config_file)

    @pytest.mark.asyncio
    async def test_load_config_yaml_async(self, tmp_path: Path) -> None:
        """YAML config loading should use async file access."""
        config_file = tmp_path / "application.yaml"
        config_file.write_text("project:\n  name: async-test\n")

        data = await load_config_yaml_async(config_file)

        assert data["project"]["name"] == "async-test"

    @pytest.mark.asyncio
    async def test_cli_context_load_config_async(self, tmp_path: Path) -> None:
        """CLI context should expose async config loading path."""
        config_file = tmp_path / "application.yaml"
        config_file.write_text("project:\n  name: context-test\n")

        ctx = CLIContext(config_path=config_file)
        data = await ctx.load_config_data()

        assert data["project"]["name"] == "context-test"

    def test_config_init_avoids_sync_open(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """`quadkit config init` should not rely on blocking open()."""
        runner = CliRunner()
        output_file = tmp_path / "quadkit.generated.yaml"

        def _fail_open(*args: object, **kwargs: object) -> None:
            raise AssertionError("blocking open() should not be used")

        monkeypatch.setattr(config_command, "open", _fail_open, raising=False)

        result = runner.invoke(
            config_command.app,
            ["init", "--output", str(output_file)],
            catch_exceptions=False,
        )

        assert result.exit_code == 0
        assert output_file.exists()
