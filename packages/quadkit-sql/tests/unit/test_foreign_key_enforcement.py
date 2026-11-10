"""Runtime foreign-key enforcement on the SQLite provider stack.

SQLite parses ``FOREIGN KEY`` clauses but enforces them only when each
connection sets ``PRAGMA foreign_keys=ON``. The provider enables it at
the one connection birthplace, so constraint violations surface as the
typed ``IntegrityError`` family from every write verb — the behaviour
generated repositories map to domain outcomes. These tests boot a real
``DatabaseService`` over a temp file, the same stack a generated
application resolves as ``DatabaseProviderProtocol``.
"""

from __future__ import annotations

import pytest

from quadkit.sql.exceptions import DuplicateKeyError, ForeignKeyError
from quadkit.sql.providers.database_service import DatabaseService

_DDL = [
    (
        "CREATE TABLE authors ("
        " id TEXT PRIMARY KEY,"
        " email TEXT NOT NULL UNIQUE,"
        " name TEXT NOT NULL)"
    ),
    (
        "CREATE TABLE posts ("
        " id TEXT PRIMARY KEY,"
        " author_id TEXT NOT NULL REFERENCES authors(id) ON DELETE RESTRICT,"
        " title TEXT NOT NULL)"
    ),
    (
        "CREATE TABLE comments ("
        " id TEXT PRIMARY KEY,"
        " post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,"
        " body TEXT NOT NULL)"
    ),
]


async def _booted_service(db_path: str) -> DatabaseService:
    service = DatabaseService(config=f"sqlite+aiosqlite:///{db_path}")
    await service.boot()
    for statement in _DDL:
        await service.execute(statement, [])
    return service


async def _seed_author_and_post(service: DatabaseService) -> None:
    await service.execute_insert(
        "authors", {"id": "a1", "email": "a@example.com", "name": "A"}
    )
    await service.execute_insert(
        "posts", {"id": "p1", "author_id": "a1", "title": "Hello"}
    )


class TestForeignKeyEnforcement:
    @pytest.fixture
    def db_path(self, tmp_path):
        return str(tmp_path / "fk.db")

    @pytest.mark.asyncio
    async def test_foreign_keys_pragma_is_on(self, db_path):
        service = await _booted_service(db_path)
        try:
            result = await service.execute_query("PRAGMA foreign_keys")
            assert list(result.rows[0].values()) == [1]
        finally:
            await service.shutdown()

    @pytest.mark.asyncio
    async def test_insert_with_missing_parent_raises_typed_error(self, db_path):
        service = await _booted_service(db_path)
        try:
            with pytest.raises(ForeignKeyError):
                await service.execute_insert(
                    "posts", {"id": "p1", "author_id": "ghost", "title": "x"}
                )
        finally:
            await service.shutdown()

    @pytest.mark.asyncio
    async def test_update_to_missing_parent_raises_typed_error(self, db_path):
        service = await _booted_service(db_path)
        try:
            await _seed_author_and_post(service)
            with pytest.raises(ForeignKeyError):
                await service.execute_update(
                    "posts", {"author_id": "ghost"}, '"id" = ?', ["p1"]
                )
        finally:
            await service.shutdown()

    @pytest.mark.asyncio
    async def test_restricted_delete_raises_typed_error(self, db_path):
        service = await _booted_service(db_path)
        try:
            await _seed_author_and_post(service)
            with pytest.raises(ForeignKeyError):
                await service.execute_delete("authors", '"id" = ?', ["a1"])
        finally:
            await service.shutdown()

    @pytest.mark.asyncio
    async def test_cascade_delete_removes_children(self, db_path):
        service = await _booted_service(db_path)
        try:
            await _seed_author_and_post(service)
            await service.execute_insert(
                "comments", {"id": "c1", "post_id": "p1", "body": "nice"}
            )
            await service.execute_delete("posts", '"id" = ?', ["p1"])
            result = await service.execute_query(
                "SELECT COUNT(*) AS n FROM comments"
            )
            assert list(result.rows[0].values()) == [0]
        finally:
            await service.shutdown()

    @pytest.mark.asyncio
    async def test_unique_collision_raises_typed_error_on_insert_and_update(
        self, db_path
    ):
        service = await _booted_service(db_path)
        try:
            await service.execute_insert(
                "authors", {"id": "a1", "email": "a@example.com", "name": "A"}
            )
            await service.execute_insert(
                "authors", {"id": "a2", "email": "b@example.com", "name": "B"}
            )
            with pytest.raises(DuplicateKeyError):
                await service.execute_insert(
                    "authors",
                    {"id": "a3", "email": "a@example.com", "name": "C"},
                )
            with pytest.raises(DuplicateKeyError):
                await service.execute_update(
                    "authors", {"email": "a@example.com"}, '"id" = ?', ["a2"]
                )
        finally:
            await service.shutdown()
