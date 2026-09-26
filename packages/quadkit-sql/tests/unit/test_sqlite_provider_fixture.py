"""In-process SQLite fixture tests — no Docker, no live database services."""

from __future__ import annotations

from typing import cast

from quadkit.sql.repositories import GenericRepository
from quadkit.sql.providers.sqlite_provider import SQLiteProvider

Entity = dict[str, object]


class TestSqliteProviderFixture:
    """GenericRepository + SQLiteProvider work entirely in-process."""

    async def _create_entities_table(self, provider: SQLiteProvider) -> None:
        await provider.execute_query("DROP TABLE IF EXISTS entities")
        await provider.execute_query(
            "CREATE TABLE entities ("
            "id TEXT PRIMARY KEY, name TEXT, created_at TEXT, updated_at TEXT)",
        )

    def _repository(self, provider: SQLiteProvider) -> GenericRepository[Entity, str]:
        return cast(
            "GenericRepository[Entity, str]",
            GenericRepository(
                provider=provider,
                table_name="entities",
                entity_class=dict,
                key_field="id",
            ),
        )

    async def test_provider_is_in_process(self, sqlite_provider: SQLiteProvider) -> None:
        """The fixture yields a connected provider that answers queries."""
        result = await sqlite_provider.execute_query("SELECT 1")
        assert result.row_count == 1

        health = await sqlite_provider.health_check()
        assert health.status.value == "healthy"

    async def test_repository_round_trip(self, sqlite_provider: SQLiteProvider) -> None:
        """GenericRepository create/find/delete round-trip without any service."""
        await self._create_entities_table(sqlite_provider)
        repo = self._repository(sqlite_provider)

        await repo.create({"id": "fixture-1", "name": "alice"})

        found = await repo.find_by_id("fixture-1")
        assert found is not None
        assert found["name"] == "alice"

        all_entities = await repo.find_many()
        assert len(all_entities) == 1
        assert all_entities[0]["name"] == "alice"

        assert await repo.delete("fixture-1") is True
        assert await repo.find_by_id("fixture-1") is None

    async def test_fixture_is_fresh_per_test(
        self, sqlite_provider: SQLiteProvider
    ) -> None:
        """Each test receives a fresh in-memory database via the fixture."""
        result = await sqlite_provider.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table'",
        )
        assert result.row_count == 0

    async def test_transaction_commit_and_rollback(
        self, sqlite_provider: SQLiteProvider
    ) -> None:
        """Queries inside an active transaction do not deadlock (regression)."""
        await self._create_entities_table(sqlite_provider)

        async with sqlite_provider.transaction():
            await sqlite_provider.execute_insert(
                "entities",
                {"id": "tx-1", "name": "committed"},
            )
        rows = await sqlite_provider.execute_query(
            "SELECT name FROM entities WHERE id = ?",
            ["tx-1"],
        )
        assert rows.row_count == 1

        try:
            async with sqlite_provider.transaction():
                await sqlite_provider.execute_insert(
                    "entities",
                    {"id": "tx-2", "name": "rolled-back"},
                )
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass

        rolled_back = await sqlite_provider.execute_query(
            "SELECT name FROM entities WHERE id = ?",
            ["tx-2"],
        )
        assert rolled_back.row_count == 0