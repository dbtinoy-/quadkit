"""Tests for the database-backed lock and secret stores (provider doubles)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from quadkit.sql.stores.locks import DatabaseLockStore
from quadkit.sql.stores.secrets import DatabaseSecretStore


class _FakeProvider:
    """Records execute/fetch/fetchrow calls; rows and tags are scripted."""

    def __init__(self, rows: list | None = None, tag: str = "OK 1") -> None:
        self.rows = rows or []
        self.tag = tag
        self.executed: list[tuple[str, tuple]] = []
        self.release_called: bool = False

    async def acquire(self):
        return self

        self.release_called = False

    async def release(self, conn):
        assert conn is self
        self.release_called = True

    async def execute(self, sql: str, *params) -> str:
        self.executed.append((sql, params))
        if "CREATE TABLE" in sql:
            return "CREATE TABLE"
        if "INSERT" in sql:
            return self.tag
        if "UPDATE" in sql:
            return self.tag
        if "DELETE" in sql:
            return self.tag
        return "OK"

    async def fetchrow(self, sql: str, *params):
        self.executed.append((sql, params))
        return self.rows[0] if self.rows else None

    async def fetch(self, sql: str, *params):
        self.executed.append((sql, params))
        return self.rows

    def statements(self) -> list[str]:
        return [sql for sql, _ in self.executed]


class TestLockStoreEnsureTable:
    async def test_creates_table_once(self) -> None:
        db = _FakeProvider()
        store = DatabaseLockStore(db, table_name="my_locks")
        await store.acquire("l", "owner-a", 30)
        await store.release("l", "owner-a")
        creates = [s for s in db.statements() if "CREATE TABLE" in s]
        assert len(creates) == 1
        assert "my_locks" in creates[0]
        assert "lock_name" in creates[0]
        assert "expires_at" in creates[0]

    async def test_no_create_when_disabled(self) -> None:
        db = _FakeProvider()
        store = DatabaseLockStore(db, auto_create_tables=False)
        await store.acquire("l", "owner-a", 30)
        assert not [s for s in db.statements() if "CREATE TABLE" in s]


class TestLockAcquire:
    async def test_acquire_success_insert(self) -> None:
        db = _FakeProvider(tag="INSERT 0 1")
        store = DatabaseLockStore(db)
        assert await store.acquire("l1", "owner-a", 60) is True

    async def test_acquire_conflict_not_expired(self) -> None:
        future = datetime.now(UTC) + timedelta(minutes=5)
        db = _FakeProvider(
            tag="INSERT 0 0",
            rows=[{
            "expires_at": future
        }],
        )
        store = DatabaseLockStore(db)
        assert await store.acquire("l1", "owner-b", 60) is False

    async def test_acquire_reclaim_expired(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=5)
        db = _FakeProvider(tag="UPDATE 1", rows=[{
            "expires_at": past
        }])
        store = DatabaseLockStore(db)
        assert await store.acquire("l1", "owner-b", 60) is True
        updates = [s for s in db.statements() if s.strip().startswith("UPDATE")]
        assert len(updates) == 1
        assert "expires_at < NOW()" in updates[0]

    async def test_acquire_expired_claim_race_lost(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=5)
        db = _FakeProvider(tag="UPDATE 0", rows=[{
            "expires_at": past
        }])
        store = DatabaseLockStore(db)
        assert await store.acquire("l1", "owner-b", 60) is False

    async def test_acquire_missing_row(self) -> None:
        db = _FakeProvider(tag="INSERT 0 0", rows=[])
        store = DatabaseLockStore(db)
        assert await store.acquire("l1", "owner-a", 60) is False

    async def test_ttl_passed_as_expires_param(self) -> None:
        db = _FakeProvider(tag="INSERT 0 1")
        store = DatabaseLockStore(db)
        await store.acquire("l1", "owner-a", 120)
        sql, params = db.executed[1]  # 0 = CREATE TABLE
        assert "expires_at" in sql
        assert "$3" in sql
        assert isinstance(params[2], datetime)

    async def test_error_propagates(self) -> None:
        db = _FakeProvider(tag="INSERT 0 1")

        async def boom(sql: str, *params: object) -> str:
            msg = "db down"
            raise RuntimeError(msg)

        db.execute = boom  # type: ignore[method-assign]
        store = DatabaseLockStore(db, auto_create_tables=False)
        with pytest.raises(RuntimeError, match="db down"):
            await store.acquire("l1", "owner-a", 60)
        assert db.release_called is True


class TestLockReleaseExtend:
    async def test_release_owned(self) -> None:
        db = _FakeProvider(tag="DELETE 1")
        store = DatabaseLockStore(db)
        assert await store.release("l1", "owner-a") is True
        sql, params = db.executed[1]
        assert "DELETE FROM" in sql
        assert "owner" in sql
        assert params == ("l1", "owner-a")

    async def test_release_wrong_owner(self) -> None:
        db = _FakeProvider(tag="DELETE 0")
        store = DatabaseLockStore(db)
        assert await store.release("l1", "intruder") is False

    async def test_extend_owned(self) -> None:
        db = _FakeProvider(tag="UPDATE 1")
        store = DatabaseLockStore(db)
        assert await store.extend("l1", "owner-a", 300) is True

    async def test_extend_wrong_owner(self) -> None:
        db = _FakeProvider(tag="UPDATE 0")
        store = DatabaseLockStore(db)
        assert await store.extend("l1", "intruder", 300) is False

    async def test_extend_params(self) -> None:
        db = _FakeProvider(tag="UPDATE 1")
        store = DatabaseLockStore(db)
        await store.extend("l1", "owner-a", 45)
        sql, params = db.executed[1]
        assert "expires_at = $3" in sql
        assert isinstance(params[2], datetime)


class TestSecretStore:
    async def test_get_found(self) -> None:
        db = _FakeProvider(rows=[{"value": "s3cret"}])
        store = DatabaseSecretStore(db, table_name="vault")
        assert await store.get("api_key") == "s3cret"

    async def test_get_missing(self) -> None:
        db = _FakeProvider(rows=[])
        store = DatabaseSecretStore(db)
        assert await store.get("nope") is None

    async def test_get_uses_table_and_param(self) -> None:
        db = _FakeProvider(rows=[{"value": "v"}])
        store = DatabaseSecretStore(db, table_name="vault")
        await store.get("api_key")
        sql, params = db.executed[1]
        assert "FROM vault" in sql
        assert params == ("api_key",)

    async def test_set_upsert(self) -> None:
        db = _FakeProvider()
        store = DatabaseSecretStore(db)
        await store.set("api_key", "v1")
        await store.set("api_key", "v2")  # overwrite
        inserts = [s for s in db.statements() if "INSERT" in s]
        assert len(inserts) == 2
        assert "ON CONFLICT (name) DO UPDATE" in inserts[0]

    async def test_get_bulk(self) -> None:
        db = _FakeProvider(
            rows=[
                {
                "name": "a",
                "value": "1",
            },
                {
                "name": "c",
                "value": "3",
            },
            ],
        )
        store = DatabaseSecretStore(db)
        result = await store.get_bulk("a", "b", "c")
        assert result == {"a": "1", "c": "3"}
        sql, params = db.executed[1]
        assert "ANY($1)" in sql
        assert params == (["a", "b", "c"],)

    async def test_get_bulk_empty(self) -> None:
        db = _FakeProvider()
        store = DatabaseSecretStore(db, auto_create_tables=False)
        assert await store.get_bulk() == {}
        assert db.executed == []

    async def test_delete(self) -> None:
        db = _FakeProvider()
        store = DatabaseSecretStore(db, table_name="vault")
        await store.delete("api_key")
        sql, params = db.executed[1]
        assert "DELETE FROM vault" in sql
        assert params == ("api_key",)

    async def test_create_table_once_and_schema(self) -> None:
        db = _FakeProvider()
        store = DatabaseSecretStore(db)
        await store.get("a")
        await store.set("b", "x")
        await store.delete("c")
        creates = [s for s in db.statements() if "CREATE TABLE" in s]
        assert len(creates) == 1
        assert "name" in creates[0]
        assert "updated_at" in creates[0]

    async def test_no_create_when_disabled(self) -> None:
        db = _FakeProvider(rows=[{"value": "v"}])
        store = DatabaseSecretStore(db, auto_create_tables=False)
        await store.get("a")
        assert not [s for s in db.statements() if "CREATE TABLE" in s]
