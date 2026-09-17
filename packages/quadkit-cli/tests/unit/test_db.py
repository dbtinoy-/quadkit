"""Tests for the db command."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from quadkit.cli.commands.db import app


class TestDbCommand:
    """Test the db command functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI test runner."""
        return CliRunner()

    def test_db_init(self, runner: CliRunner, tmp_path: Path, monkeypatch):
        """Test db init command."""
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["init", "custom_migrations"])
        assert result.exit_code == 0
        assert "Created custom_migrations directory" in result.output
        assert tmp_path.joinpath("custom_migrations").exists()

    @patch(
        "quadkit.cli.commands.db_bootstrap.get_migration_manager",
        new_callable=AsyncMock,
    )
    def test_db_migrate_create(
        self, mock_get_manager, runner: CliRunner, tmp_path: Path
    ):
        """Test db migrate (create) command."""
        mock_manager = AsyncMock()
        mock_manager.create_migration.return_value = "20230101_000000"
        mock_get_manager.return_value = mock_manager

        result = runner.invoke(app, ["migrate", "test_migration"])
        assert result.exit_code == 0
        assert "Created migration 20230101_000000: test_migration" in result.output
        mock_manager.create_migration.assert_called_once_with(
            "test_migration", "-- Add your SQL here"
        )

    @patch(
        "quadkit.cli.commands.db_bootstrap._bootstrap_migration_runner",
        new_callable=AsyncMock,
    )
    def test_db_upgrade(self, mock_bootstrap, runner: CliRunner, tmp_path: Path):
        """Test db upgrade command."""
        mock_runner = AsyncMock()
        mock_runner.run_migrations.return_value = ["20230101_000000"]
        mock_orchestrator = AsyncMock()
        mock_container = AsyncMock()
        mock_bootstrap.return_value = (mock_runner, mock_orchestrator, mock_container)

        result = runner.invoke(app, ["upgrade"])
        assert result.exit_code == 0
        assert "Applied 20230101_000000" in result.output
        mock_runner.run_migrations.assert_called_once()
        mock_orchestrator.shutdown_all.assert_called_once()

    @patch(
        "quadkit.cli.commands.db_bootstrap._bootstrap_migration_runner",
        new_callable=AsyncMock,
    )
    def test_db_status(self, mock_bootstrap, runner: CliRunner, tmp_path: Path):
        """Test db status command."""
        mock_runner = AsyncMock()
        mock_runner.get_current_version.return_value = None
        mock_runner.get_pending_migrations.return_value = []
        mock_orchestrator = AsyncMock()
        mock_container = AsyncMock()
        mock_bootstrap.return_value = (mock_runner, mock_orchestrator, mock_container)

        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert (
            "Schema is up to date" in result.output
            or "No migrations applied" in result.output
        )
        mock_orchestrator.shutdown_all.assert_called_once()

    @patch(
        "quadkit.cli.commands.db_bootstrap.get_migration_manager",
        new_callable=AsyncMock,
    )
    def test_db_seed(
        self, mock_get_manager, runner: CliRunner, tmp_path: Path, monkeypatch
    ):
        """Test db seed command."""
        mock_manager = AsyncMock()
        mock_manager.provider = AsyncMock()
        mock_get_manager.return_value = mock_manager

        # Create a dummy seeder file
        monkeypatch.chdir(tmp_path)
        seeds_dir = tmp_path / "seeds"
        seeds_dir.mkdir()
        (seeds_dir / "test_seeder.py").write_text("def run(provider): pass")

        result = runner.invoke(app, ["seed"])
        assert result.exit_code == 0
        assert "Running seeder: seeds/test_seeder.py" in result.output

    @patch(
        "quadkit.cli.commands.db_bootstrap.get_migration_manager",
        new_callable=AsyncMock,
    )
    def test_db_reset(self, mock_get_manager, runner: CliRunner, tmp_path: Path):
        """Test db reset command."""
        mock_manager = AsyncMock()
        mock_manager.provider = AsyncMock()
        mock_manager.provider.url = "sqlite:///dev.db"
        mock_manager.provider.execute_query.return_value = MagicMock(rows=[])
        mock_get_manager.return_value = mock_manager

        result = runner.invoke(app, ["reset", "--force"])
        assert result.exit_code == 0
        assert "Database cleared" in result.output
        mock_manager.initialize_migration_table.assert_called_once()


@pytest.mark.asyncio
async def test_bootstrap_db_provider_resolves_usable_provider(
    tmp_path: Path, monkeypatch
):
    """_bootstrap_db_provider() resolves a usable DatabaseProviderProtocol."""
    from quadkit.cli.package_names import module_for

    pytest.importorskip(module_for("sql"))
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from quadkit.cli.commands.db_bootstrap import _bootstrap_db_provider

    provider, db_provider = await _bootstrap_db_provider()

    assert await provider.table_exists("does_not_exist") is False
    await db_provider.shutdown()


def _empty_contributor_runtime(*_args, **_kwargs) -> "ContributorRuntime":
    """Return an empty ContributorRuntime regardless of call arguments."""
    from quadkit.cli.contributors.runtime import ContributorRuntime

    return ContributorRuntime()


def test_db_setup_reports_nothing_to_do_when_no_contributions(monkeypatch):
    """db setup reports nothing to do when no contributions are discovered."""
    from quadkit.cli.contributors import runtime as runtime_module

    runner = CliRunner()

    monkeypatch.setattr(
        runtime_module.ContributorRuntime,
        "from_entry_points",
        classmethod(_empty_contributor_runtime),
    )

    result = runner.invoke(app, ["setup"])

    assert result.exit_code == 0
    assert "Nothing to do" in result.stdout
