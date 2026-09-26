import sys
import pytest
from unittest.mock import AsyncMock, Mock, patch

from quadkit.sql.migrations.manager import AlembicManager

@pytest.fixture
def mock_alembic_components(monkeypatch):
    """Mock the AlembicManager's internal components."""
    monkeypatch.setattr("quadkit.sql.migrations.manager._alembic.ALEMBIC_AVAILABLE", True)

    with patch("quadkit.sql.migrations.manager._alembic.Config") as MockConfig, \
         patch("quadkit.sql.migrations.manager._alembic.MigrationEngine") as MockEngine, \
         patch("quadkit.sql.migrations.manager._alembic.SchemaIntrospector") as MockIntrospector, \
         patch("quadkit.sql.migrations.manager._alembic.MigrationOrchestrator") as MockOrchestrator:

        mock_config = MockConfig.return_value
        mock_engine = MockEngine.return_value
        mock_introspector = MockIntrospector.return_value
        mock_orchestrator = MockOrchestrator.return_value

        # Make all async methods into AsyncMocks
        mock_orchestrator.initialize_migration_table = AsyncMock()
        mock_engine.upgrade = AsyncMock()
        mock_engine.downgrade = AsyncMock()
        mock_engine.upgrade_dry_run = AsyncMock(return_value=["UPGRADE SQL"])
        mock_engine.downgrade_dry_run = AsyncMock(return_value=["DOWNGRADE SQL"])
        mock_engine.create_revision = AsyncMock(return_value="rev_123")
        mock_engine.create_branch = AsyncMock(return_value="branch_123")
        mock_engine.merge_branches = AsyncMock(return_value="merge_123")
        mock_engine.stamp = AsyncMock()
        mock_engine.edit = AsyncMock()
        mock_engine.squash = AsyncMock(return_value="squash_123")

        mock_introspector.get_status = AsyncMock(return_value="status")
        mock_introspector.get_history = AsyncMock(return_value=["hist_entry"])
        mock_introspector.get_branches = AsyncMock(return_value=["branch_x"])
        mock_introspector.validate_migrations = AsyncMock(return_value={"valid": True})
        mock_introspector.get_pending_operations = AsyncMock(return_value=[])

        # Mock alembic modules that are imported dynamically during tests
        with patch.dict(sys.modules, {
            "alembic": Mock(),
            "alembic.command": Mock(),
            "alembic.util.exc": Mock(),
        }):
            yield {
                "config": mock_config,
                "engine": mock_engine,
                "introspector": mock_introspector,
                "orchestrator": mock_orchestrator,
            }

@pytest.fixture
def manager(mock_alembic_components, tmp_path):
    """Create a test manager instance."""
    return AlembicManager("sqlite:///:memory:", tmp_path)

@pytest.mark.asyncio
async def test_initialize(manager, mock_alembic_components):
    await manager.initialize()
    mock_alembic_components["orchestrator"].initialize_migration_table.assert_awaited_once()

@pytest.mark.asyncio
async def test_upgrade(manager, mock_alembic_components):
    await manager.upgrade("head_rev")
    mock_alembic_components["engine"].upgrade.assert_awaited_once_with("head_rev")

@pytest.mark.asyncio
async def test_downgrade(manager, mock_alembic_components):
    await manager.downgrade("base_rev")
    mock_alembic_components["engine"].downgrade.assert_awaited_once_with("base_rev")

@pytest.mark.asyncio
async def test_upgrade_dry_run(manager, mock_alembic_components):
    result = await manager.upgrade_dry_run("head_rev")
    assert result == ["UPGRADE SQL"]
    mock_alembic_components["engine"].upgrade_dry_run.assert_awaited_once_with("head_rev")

@pytest.mark.asyncio
async def test_downgrade_dry_run(manager, mock_alembic_components):
    result = await manager.downgrade_dry_run("base_rev")
    assert result == ["DOWNGRADE SQL"]
    mock_alembic_components["engine"].downgrade_dry_run.assert_awaited_once_with("base_rev")

@pytest.mark.asyncio
async def test_get_status(manager, mock_alembic_components):
    result = await manager.get_status()
    assert result == "status"
    mock_alembic_components["introspector"].get_status.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_history(manager, mock_alembic_components):
    result = await manager.get_history(limit=5)
    assert result == ["hist_entry"]
    mock_alembic_components["introspector"].get_history.assert_awaited_once_with(5)

@pytest.mark.asyncio
async def test_get_branches(manager, mock_alembic_components):
    result = await manager.get_branches()
    assert result == ["branch_x"]
    mock_alembic_components["introspector"].get_branches.assert_awaited_once()

@pytest.mark.asyncio
async def test_create_revision(manager, mock_alembic_components):
    result = await manager.create_revision("msg")
    assert result == "rev_123"
    mock_alembic_components["engine"].create_revision.assert_awaited_once_with("msg")

@pytest.mark.asyncio
async def test_create_branch(manager, mock_alembic_components):
    result = await manager.create_branch("feature", message="msg")
    assert result == "branch_123"
    mock_alembic_components["engine"].create_branch.assert_awaited_once_with("feature", message="msg")

@pytest.mark.asyncio
async def test_merge_branches(manager, mock_alembic_components):
    result = await manager.merge_branches("b1", "b2", message="msg")
    assert result == "merge_123"
    mock_alembic_components["engine"].merge_branches.assert_awaited_once_with("b1", "b2", message="msg")

@pytest.mark.asyncio
async def test_stamp(manager, mock_alembic_components):
    await manager.stamp("rev1")
    mock_alembic_components["engine"].stamp.assert_awaited_once_with("rev1")

@pytest.mark.asyncio
async def test_edit(manager, mock_alembic_components):
    await manager.edit("rev1")
    mock_alembic_components["engine"].edit.assert_awaited_once_with("rev1")

@pytest.mark.asyncio
async def test_squash(manager, mock_alembic_components):
    result = await manager.squash(["rev1", "rev2"], "msg")
    assert result == "squash_123"
    mock_alembic_components["engine"].squash.assert_awaited_once_with(["rev1", "rev2"], "msg")

@pytest.mark.asyncio
async def test_validate_migrations(manager, mock_alembic_components):
    result = await manager.validate_migrations()
    assert result == {"valid": True}
    mock_alembic_components["introspector"].validate_migrations.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_pending_operations(manager, mock_alembic_components):
    result = await manager.get_pending_operations()
    assert result == []
    mock_alembic_components["introspector"].get_pending_operations.assert_awaited_once()

@pytest.mark.asyncio
async def test_initialize_migration_table(manager, mock_alembic_components):
    await manager.initialize_migration_table()
    mock_alembic_components["orchestrator"].initialize_migration_table.assert_awaited_once()
