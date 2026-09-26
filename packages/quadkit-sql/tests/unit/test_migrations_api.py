from pathlib import Path
import sys

# Removed legacy sys.path manipulation

from unittest.mock import AsyncMock, patch

import pytest

from quadkit.sql.migrations import api as migrations_api


@pytest.mark.asyncio
async def test_init_migrations_calls_initialize():
    mock_manager = AsyncMock()
    # Configure AsyncMock instance to have initialize coroutine
    mock_manager.initialize = AsyncMock()

    with patch("quadkit.sql.migrations.api.AlembicManager", return_value=mock_manager):
        manager = await migrations_api.init_migrations("sqlite:///:memory:")

    # ensure initialize was awaited and the manager returned
    mock_manager.initialize.assert_awaited()
    assert manager is mock_manager


@pytest.mark.asyncio
async def test_create_migration_delegates_to_manager():
    mock_manager = AsyncMock()
    mock_manager.create_revision = AsyncMock(return_value="rev1")

    with patch("quadkit.sql.migrations.api.AlembicManager", return_value=mock_manager):
        rev = await migrations_api.create_migration(
            "sqlite:///:memory:", "migrations", "msg", autogenerate=True,
        )

    mock_manager.create_revision.assert_awaited_with("msg", autogenerate=True)
    assert rev == "rev1"
