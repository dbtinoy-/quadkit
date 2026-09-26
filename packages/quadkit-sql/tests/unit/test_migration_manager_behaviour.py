from pathlib import Path

import pytest

from quadkit.sql.migrations.manager import SimpleMigrationManager


@pytest.mark.asyncio
async def test_apply_pending_migrations_with_alembic_revisions_returns_empty(tmp_path):
    # Point the migration manager to an existing directory with python/alembic revisions
    repo_versions = Path(__file__).resolve().parents[3] / "migrations" / "versions"

    manager = SimpleMigrationManager(provider=None, migrations_dir=str(repo_versions))

    # Should return empty list since SimpleMigrationManager only looks for .sql files
    applied = await manager.apply_pending_migrations()

    assert applied == []
