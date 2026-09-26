"""Repository compliance test backed by ``postgres_provider``.

The fixture uses a real PostgreSQL when reachable and an in-process SQLite
provider otherwise, so this compliance round-trip runs without a pre-started
Docker Compose stack.
"""

from __future__ import annotations

from typing import cast

import pytest

from quadkit.sql.providers.postgres_provider import PostgresProvider
from quadkit.sql.providers.sqlite_provider import SQLiteProvider
from quadkit.sql.repositories import GenericRepository

pytestmark = [pytest.mark.integration, pytest.mark.requires_postgres]

Entity = dict[str, object]
Provider = SQLiteProvider | PostgresProvider


class TestPostgresRepositoryCompliance:
    """Verify GenericRepository save/find/delete against postgres_provider."""

    @pytest.fixture(autouse=True)
    async def _create_entities_table(self, postgres_provider: Provider) -> None:
        """Reset the entities table for every test."""
        await postgres_provider.execute_query("DROP TABLE IF EXISTS entities")
        await postgres_provider.execute_query(
            "CREATE TABLE entities ("
            "id TEXT PRIMARY KEY, name TEXT, created_at TEXT, updated_at TEXT)",
        )

    def _repository(self, postgres_provider: Provider) -> GenericRepository[Entity, str]:
        """Build a GenericRepository over the fixture provider."""
        return cast(
            "GenericRepository[Entity, str]",
            GenericRepository(
                provider=postgres_provider,
                table_name="entities",
                entity_class=dict,
                key_field="id",
            ),
        )

    async def test_save_and_find(self, postgres_provider: Provider) -> None:
        """create() and find_by_id() round-trip an entity."""
        repo = self._repository(postgres_provider)
        entity: Entity = {"id": "test-123", "name": "Test Entity"}

        await repo.create(entity)

        found = await repo.find_by_id("test-123")

        assert found is not None
        assert found["id"] == "test-123"
        assert found["name"] == "Test Entity"

    async def test_delete_removes_entity(self, postgres_provider: Provider) -> None:
        """delete() removes an entity from storage."""
        repo = self._repository(postgres_provider)
        entity: Entity = {"id": "test-456", "name": "To Delete"}

        await repo.create(entity)

        deleted = await repo.delete("test-456")
        assert deleted is True

        assert await repo.find_by_id("test-456") is None

    async def test_find_many_returns_list(self, postgres_provider: Provider) -> None:
        """find_many() returns all created entities."""
        repo = self._repository(postgres_provider)

        await repo.create({"id": "test-1", "name": "One"})
        await repo.create({"id": "test-2", "name": "Two"})

        all_entities = await repo.find_many()

        ids = [e["id"] for e in all_entities]
        assert "test-1" in ids
        assert "test-2" in ids