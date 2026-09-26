"""Tests for SQLAlchemyOAuthIdentityStore CRUD + resolution flows."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.auth.storage.oauth_identity_store import SQLAlchemyOAuthIdentityStore


class _Result:
    def __init__(self, rows: list[dict] | None = None, row_count: int = 0) -> None:
        self.rows = rows or []
        self.row_count = row_count


@pytest.fixture
def db() -> MagicMock:
    conn = AsyncMock()
    db = MagicMock()
    db.get_scoped_connection = AsyncMock(return_value=conn)

    class _Ctx:
        async def __aenter__(self) -> None:
            return None

        async def __aexit__(self, *a: object) -> bool:
            return False

    db.scoped_context = MagicMock(return_value=_Ctx())
    return db


@pytest.fixture
def store(db: MagicMock) -> SQLAlchemyOAuthIdentityStore:
    return SQLAlchemyOAuthIdentityStore(db)


def _row(user_id: str = "u1", provider: str = "google", ext: str = "ext-1") -> dict:
    return {
        "user_id": user_id,
        "provider": provider,
        "provider_user_id": ext,
        "created_at": None,
        "updated_at": None,
    }


class TestEnsureTables:
    async def test_ddl_executed_once_per_store(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        await store._ensure_tables()
        await store._ensure_tables()
        conn = db.get_scoped_connection.return_value
        assert conn.execute.call_count == 2
        # first call: table + index (two statements)
        first_calls = [c[0][0] for c in conn.execute.call_args_list]
        assert any("CREATE TABLE" in s for s in first_calls)
        assert any("CREATE INDEX" in s for s in first_calls)

    async def test_fresh_store_recreates(self, db: MagicMock) -> None:
        store_a = SQLAlchemyOAuthIdentityStore(db)
        await store_a._ensure_tables()
        db.get_scoped_connection.return_value.reset_mock()
        store_b = SQLAlchemyOAuthIdentityStore(db)
        await store_b._ensure_tables()
        assert db.get_scoped_connection.return_value.execute.call_count == 2


class TestCreate:
    async def test_create_returns_identity(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(row_count=1)
        identity = await store.create_oauth_identity("u1", "github", "gh-42")
        assert identity.user_id == "u1"
        assert identity.provider == "github"
        assert identity.provider_user_id == "gh-42"
        assert identity.created_at is not None
        assert identity.updated_at is not None

    async def test_insert_binds_all_columns(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(row_count=1)
        await store.create_oauth_identity("u9", "okta", "ok-7")
        conn = db.get_scoped_connection.return_value
        sql, params = conn.execute.call_args[0]
        assert "INSERT INTO oauth_identities" in sql
        assert params[0] == "u9"
        assert params[1] == "okta"
        assert params[2] == "ok-7"


class TestGet:
    async def test_found(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(rows=[_row()])
        identity = await store.get_oauth_identity("google", "ext-1")
        assert identity is not None
        assert identity.user_id == "u1"

    async def test_missing(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(rows=[])
        assert await store.get_oauth_identity("google", "nope") is None

    async def test_for_user(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        rows = [_row(provider="google"), _row(provider="github", ext="gh-1")]
        db.get_scoped_connection.return_value.execute.return_value = _Result(rows=rows)
        identities = await store.get_oauth_identities_for_user("u1")
        assert [i.provider for i in identities] == ["google", "github"]

    async def test_for_user_empty(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(rows=[])
        assert await store.get_oauth_identities_for_user("u1") == []


class TestDelete:
    async def test_delete_found(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(row_count=1)
        assert await store.delete_oauth_identity("google", "ext-1") is True

    async def test_delete_missing(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(row_count=0)
        assert await store.delete_oauth_identity("google", "nope") is False

    async def test_delete_for_user_counts(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(row_count=3)
        assert await store.delete_oauth_identities_for_user("u1") == 3

    async def test_delete_for_user_zero(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(row_count=0)
        assert await store.delete_oauth_identities_for_user("u1") == 0


class TestResolve:
    async def test_get_user_by_oauth_identity(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(rows=[_row()])
        assert await store.get_user_by_oauth_identity("google", "ext-1") == "u1"

    async def test_get_user_by_oauth_identity_missing(
        self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock
    ) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(rows=[])
        assert await store.get_user_by_oauth_identity("google", "nope") is None

    async def test_resolve_uuid_existing_user(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        uuid = "123e4567-e89b-12d3-a456-426614174000"
        db.get_scoped_connection.return_value.execute.return_value = _Result(rows=[{"user_id": uuid}])
        assert await store.resolve_user_id(uuid) == uuid

    async def test_resolve_uuid_unknown_user(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        uuid = "123e4567-e89b-12d3-a456-426614174000"
        db.get_scoped_connection.return_value.execute.return_value = _Result(rows=[])
        assert await store.resolve_user_id(uuid) is None

    async def test_resolve_oauth_external_id(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(rows=[_row(provider="github", ext="gh-42")])
        assert await store.resolve_user_id("gh-42", provider="github") == "u1"

    async def test_resolve_unrelated_string(self, store: SQLAlchemyOAuthIdentityStore, db: MagicMock) -> None:
        db.get_scoped_connection.return_value.execute.return_value = _Result(rows=[])
        assert await store.resolve_user_id("not-a-uuid-or-id") is None

    async def test_sync_resolution_unsupported(self, store: SQLAlchemyOAuthIdentityStore) -> None:
        assert store.resolve_user_id_sync("anything") is None
