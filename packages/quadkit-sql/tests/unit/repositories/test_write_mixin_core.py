"""Tests for SQLRepository write mixin: create, update, soft/hard delete, upsert."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.sql.exceptions import DatabaseError, ForeignKeyError
from quadkit.sql.providers.base_provider import (
    DeleteResult,
    InsertResult,
    QueryResult,
    UpdateResult,
)
from quadkit.sql.repositories.base import SQLRepository


class RecordingProvider:
    """Fake provider recording write operations."""

    def __init__(self) -> None:
        self.inserts: list[tuple[str, dict[str, Any]]] = []
        self.updates: list[tuple[str, dict[str, Any], str, list[Any]]] = []
        self.deletes: list[tuple[str, str, list[Any]]] = []
        self.queries: list[tuple[str, list[Any]]] = []
        self.insert_result = InsertResult(
            inserted_id=1, affected_rows=1, execution_time=0.0, success=True
        )
        self.update_result = UpdateResult(
            affected_rows=1, execution_time=0.0, success=True
        )
        self.delete_result = DeleteResult(
            affected_rows=1, execution_time=0.0, success=True
        )
        self.query_result = QueryResult(
            rows=[], row_count=0, execution_time=0.0, success=True
        )

    async def execute_insert(self, table: str, data: dict[str, Any]) -> InsertResult:
        self.inserts.append((table, dict(data)))
        return self.insert_result

    async def execute_update(
        self, table: str, data: dict[str, Any], where: str, params: list[Any]
    ) -> UpdateResult:
        self.updates.append((table, dict(data), where, list(params)))
        return self.update_result

    async def execute_delete(
        self, table: str, where: str, params: list[Any]
    ) -> DeleteResult:
        self.deletes.append((table, where, list(params)))
        return self.delete_result

    async def execute_query(self, query: str, params: Any = None) -> QueryResult:
        self.queries.append((query, list(params or [])))
        return self.query_result


class DictRepo(SQLRepository[dict[str, Any], int]):
    def __init__(self, provider: RecordingProvider, **kw: Any) -> None:
        super().__init__(provider, "users", **kw)

    def _entity_to_dict(self, entity: dict[str, Any]) -> dict[str, Any]:
        return dict(entity)

    def _row_to_entity(self, row: dict[str, Any]) -> dict[str, Any]:
        return dict(row)


def _repo(**kw: Any) -> tuple[DictRepo, RecordingProvider]:
    p = RecordingProvider()
    return DictRepo(p, **kw), p


class TestCreate:
    async def test_create_stamps_timestamps(self) -> None:
        repo, p = _repo()
        entity = {"name": "a"}
        result = await repo.create(entity)
        assert result is entity
        assert "created_at" in p.inserts[0][1]
        assert "updated_at" in p.inserts[0][1]
        assert p.inserts[0][0] == "users"

    async def test_create_preserves_existing_timestamps(self) -> None:
        repo, p = _repo()
        entity = {"name": "a", "created_at": "x", "updated_at": "y"}
        await repo.create(entity)
        assert p.inserts[0][1]["created_at"] == "x"
        assert p.inserts[0][1]["updated_at"] == "y"

    async def test_create_strips_unset_key(self) -> None:
        repo, p = _repo()
        await repo.create({"name": "a", "id": None})
        assert "id" not in p.inserts[0][1]

    async def test_create_sets_generated_id(self) -> None:
        repo, provider = _repo()
        entity = {"name": "a"}
        await repo.create(entity)
        assert entity["id"] == provider.insert_result.inserted_id

    async def test_create_keeps_a_caller_supplied_key(self) -> None:
        """A supplied primary key is the identity; `lastrowid` is not.

        `inserted_id` is the driver's rowid. For a table keyed by something the
        caller chose (a user id, a uuid) assigning it would replace the real
        key on the entity — which is how a created user came back with id
        ``"1"`` while the row it wrote carried the uuid.
        """
        repo, provider = _repo(key_field="user_id")
        entity = {"user_id": "8f1c-uuid", "email": "a@example.com"}
        await repo.create(entity)
        assert entity["user_id"] == "8f1c-uuid"
        assert provider.insert_result.inserted_id == 1

    async def test_create_reports_duplicate_key_as_such(self) -> None:
        """A failed insert names *which* rule it broke, not just "failed".

        ``DatabaseProviderProtocol.execute_insert`` reports failure as a result
        with the driver's message, so the exception type is gone before the
        repository sees it. Callers that treat "already exists" as an expected
        answer (idempotent webhook ledger, one redemption per user) need that
        distinction back, or they end up matching driver strings themselves.
        """
        from quadkit.sql.exceptions import DuplicateKeyError

        repo, p = _repo()
        p.insert_result = InsertResult(
            inserted_id=None,
            affected_rows=0,
            execution_time=0.0,
            success=False,
            error_message="UNIQUE constraint failed: payment_events.stripe_event_id",
        )
        with pytest.raises(DuplicateKeyError):
            await repo.create({"stripe_event_id": "evt_1"})

    async def test_create_reports_mysql_duplicate_entry(self) -> None:
        from quadkit.sql.exceptions import DuplicateKeyError

        repo, p = _repo()
        p.insert_result = InsertResult(
            inserted_id=None,
            affected_rows=0,
            execution_time=0.0,
            success=False,
            error_message="(1062, \"Duplicate entry 'evt_1' for key 'uq_events'\")",
        )
        with pytest.raises(DuplicateKeyError):
            await repo.create({"stripe_event_id": "evt_1"})

    async def test_create_reports_not_null_violation(self) -> None:
        from quadkit.sql.exceptions import NotNullViolationError

        repo, p = _repo()
        p.insert_result = InsertResult(
            inserted_id=None,
            affected_rows=0,
            execution_time=0.0,
            success=False,
            error_message="NOT NULL constraint failed: users.email",
        )
        with pytest.raises(NotNullViolationError):
            await repo.create({"name": "a"})

    async def test_create_failure_raises(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        p.insert_result = InsertResult(
            inserted_id=None,
            affected_rows=0,
            execution_time=0.0,
            success=False,
            error_message="constraint",
        )
        with pytest.raises(RepositoryError, match="constraint"):
            await repo.create({"name": "a"})

    async def test_create_db_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, provider = _repo()

        async def boom(table: str, data: dict[str, Any]) -> InsertResult:
            raise DatabaseError("db down")

        provider.execute_insert = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to create entity"):
            await repo.create({"name": "a"})

    async def test_read_only_fields_excluded(self) -> None:
        repo, p = _repo()
        repo.read_only_fields = ["created_at"]
        await repo.create({"name": "a"})
        # created_at is re-stamped then removed? Order: timestamps added,
        # then read-only fields deleted.
        data = p.inserts[0][1]
        assert data["name"] == "a"

    async def test_write_table_name_override(self) -> None:
        repo, p = _repo()
        repo.write_table_name = "users_write"
        await repo.create({"name": "a"})
        assert p.inserts[0][0] == "users_write"


class TestSoftDelete:
    async def test_soft_delete_updates_deleted_at(self) -> None:
        repo, p = _repo()
        assert await repo.soft_delete(5) is True
        table, data, where, params = p.updates[0]
        assert table == "users"
        assert "deleted_at" in data
        assert where == '"id" = ?'
        assert params == [5]

    async def test_soft_delete_failure_returns_false(self) -> None:
        repo, p = _repo()
        p.update_result = UpdateResult(
            affected_rows=0, execution_time=0.0, success=False
        )
        assert await repo.soft_delete(5) is False

    async def test_soft_delete_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()

        async def boom(*a: Any, **kw: Any) -> UpdateResult:
            raise DatabaseError("db down")

        p.execute_update = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to soft delete entity"):
            await repo.soft_delete(5)


class TestDeleteById:
    async def test_delete_by_id_success(self) -> None:
        repo, p = _repo()
        assert await repo.delete_by_id(7) is True
        table, where, params = p.deletes[0]
        assert table == "users"
        assert where == '"id" = ?'
        assert params == [7]

    async def test_delete_by_id_affected_rows_zero(self) -> None:
        repo, p = _repo()
        p.delete_result = DeleteResult(
            affected_rows=0, execution_time=0.0, success=True
        )
        assert await repo.delete_by_id(7) is False

    async def test_delete_by_id_failure_raises(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        p.delete_result = DeleteResult(
            affected_rows=0,
            execution_time=0.0,
            success=False,
            error_message="locked",
        )
        with pytest.raises(RepositoryError, match="Delete failed: locked"):
            await repo.delete_by_id(7)

    async def test_delete_db_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()

        async def boom(*a: Any, **kw: Any) -> DeleteResult:
            raise DatabaseError("db down")

        p.execute_delete = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to delete entity"):
            await repo.delete_by_id(7)


class TestUpsert:
    async def test_upsert_builds_conflict_query(self) -> None:
        repo, p = _repo()
        entity = {"email": "a@x", "name": "a"}
        result = await repo.upsert(entity)
        assert result is entity
        query, params = p.queries[0]
        assert 'INSERT INTO "users"' in query
        assert 'ON CONFLICT ("id") DO UPDATE SET' in query
        assert '"name" = EXCLUDED."name"' in query
        assert "email" in query
        assert "a@x" in params

    async def test_upsert_custom_conflict_and_update_fields(self) -> None:
        repo, p = _repo()
        await repo.upsert(
            {"email": "a@x", "name": "a", "role": "u"},
            conflict_fields=["email"],
            update_fields=["name"],
        )
        query, _ = p.queries[0]
        assert 'ON CONFLICT ("email") DO UPDATE SET' in query
        assert '"name" = EXCLUDED."name"' in query
        assert 'EXCLUDED."role"' not in query

    async def test_upsert_failure_raises(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        p.query_result = QueryResult(
            rows=[],
            row_count=0,
            execution_time=0.0,
            success=False,
            error_message="boom",
        )
        with pytest.raises(RepositoryError, match="Upsert failed: boom"):
            await repo.upsert({"email": "a@x"})

    async def test_upsert_db_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()

        async def boom(*a: Any, **kw: Any) -> QueryResult:
            raise DatabaseError("db down")

        p.execute_query = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to upsert entity"):
            await repo.upsert({"email": "a@x"})


class TestUpdate:
    async def test_update_delegates_to_standard_path(self) -> None:
        repo, p = _repo()
        entity = {"id": 3, "name": "new"}
        result = await repo.update(entity)
        assert result is entity
        assert len(p.updates) == 1
        table, data, where, params = p.updates[0]
        assert table == "users"
        assert where == '"id" = ?'
        assert params == [3]
        assert data["name"] == "new"


class MySQLDialectProvider(RecordingProvider):
    """Recording provider that reports MySQL, so the SQL shape can be pinned."""

    database_type = "mysql"


class TestUpsertDialect:
    """The upsert statement follows the provider's dialect, not one SQL flavour.

    ``ON CONFLICT`` is Postgres/SQLite syntax. MySQL answers it with a syntax
    error on the first write, which is a broken host rather than a degraded
    one — so the statement is built per dialect instead of per promise.
    """

    async def test_postgres_keeps_on_conflict(self) -> None:
        repo, p = _repo()
        await repo.upsert({"email": "a@x", "name": "a"}, conflict_fields=["email"])
        query, _ = p.queries[0]
        assert 'ON CONFLICT ("email") DO UPDATE SET' in query
        assert '"name" = EXCLUDED."name"' in query
        assert "ON DUPLICATE KEY" not in query

    async def test_mysql_uses_on_duplicate_key_update(self) -> None:
        repo = DictRepo(MySQLDialectProvider())
        provider = repo.provider
        assert isinstance(provider, RecordingProvider)
        await repo.upsert({"email": "a@x", "name": "a"}, conflict_fields=["email"])
        query, _ = provider.queries[0]
        assert "ON DUPLICATE KEY UPDATE" in query
        assert '"name" = VALUES("name")' in query
        assert "ON CONFLICT" not in query
        assert "EXCLUDED." not in query

    async def test_mysql_never_names_a_conflict_target(self) -> None:
        """MySQL infers the unique key; a column list there is a syntax error."""
        repo = DictRepo(MySQLDialectProvider())
        provider = repo.provider
        assert isinstance(provider, RecordingProvider)
        await repo.upsert({"email": "a@x", "name": "a"}, conflict_fields=["email"])
        query, _ = provider.queries[0]
        assert '("email")' not in query
        assert "DO UPDATE" not in query


class TestDeleteWhere:
    """Filtered deletion goes through the filter builder and the RLS hook."""

    async def test_equality_filters_build_a_parameterized_delete(self) -> None:
        repo, p = _repo()
        deleted = await repo.delete_where(status=2)
        assert deleted == 1
        table, where, params = p.deletes[0]
        assert table == "users"
        assert where == '"status" = ?'
        assert params == [2]

    async def test_typed_filters_express_a_range(self) -> None:
        from quadkit.sql.repositories.filter_objects import F

        repo, p = _repo()
        await repo.delete_where(F("last_seen_at") < 1000)
        _, where, params = p.deletes[0]
        assert where == '"last_seen_at" < ?'
        assert params == [1000]

    async def test_typed_filters_compose_with_keyword_filters(self) -> None:
        from quadkit.sql.repositories.filter_objects import F

        repo, p = _repo()
        await repo.delete_where(F("last_seen_at") < 1000, node_name="node-a")
        _, where, params = p.deletes[0]
        assert '"last_seen_at" < ?' in where
        assert '"node_name" = ?' in where
        assert params == [1000, "node-a"]

    async def test_soft_delete_tables_keep_tombstones_by_default(self) -> None:
        repo, p = _repo(soft_delete_enabled=True)
        await repo.delete_where(status=2)
        _, where, _ = p.deletes[0]
        assert "deleted_at IS NULL" in where

    async def test_include_deleted_purges_tombstones_too(self) -> None:
        repo, p = _repo(soft_delete_enabled=True)
        await repo.delete_where(status=2, include_deleted=True)
        _, where, _ = p.deletes[0]
        assert "deleted_at IS NULL" not in where

    async def test_no_filters_is_refused(self) -> None:
        """An empty filter is a call-site bug, not a request to purge."""
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        with pytest.raises(RepositoryError, match="at least one filter"):
            await repo.delete_where()
        assert p.deletes == []

    async def test_failure_raises_repository_error(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        p.delete_result = DeleteResult(
            affected_rows=0,
            execution_time=0.0,
            success=False,
            error_message="nope",
        )
        with pytest.raises(RepositoryError, match="Delete failed: nope"):
            await repo.delete_where(status=2)

    async def test_provider_error_is_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()

        async def boom(*a: Any, **kw: Any) -> DeleteResult:
            raise DatabaseError("db down")

        p.execute_delete = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to delete entities"):
            await repo.delete_where(status=2)


class TestUpdateWhere:
    """Conditional writes: the row is chosen by a filter, not by its key."""

    async def test_filters_become_the_where_clause(self) -> None:
        repo, p = _repo()
        changed = await repo.update_where(
            {"state": "{}"}, task_id="tsk_1", locked_by="a"
        )
        assert changed == 1
        table, data, where, params = p.updates[0]
        assert table == "users"
        assert data == {"state": "{}"}
        assert '"task_id" = ?' in where
        assert '"locked_by" = ?' in where
        assert params == ["tsk_1", "a"]

    async def test_typed_filters_reach_the_statement(self) -> None:
        from quadkit.sql.repositories.filter_objects import F

        repo, p = _repo()
        await repo.update_where(
            {"status": "failed"}, F("status").in_(("pending", "running"))
        )
        _, _, where, params = p.updates[0]
        assert where == '"status" IN (?, ?)'
        assert params == ["pending", "running"]

    async def test_delta_reaches_the_provider_untouched(self) -> None:
        """A ``Delta`` is a value the provider renders, not one to unwrap here.

        The repository hands *data* straight to ``execute_update``; if it
        flattened the ``Delta`` to its amount the statement would overwrite the
        column instead of moving it, which is the bug the type exists to stop.
        """
        from quadkit.contracts.data.identifiers import Delta

        repo, p = _repo()
        await repo.update_where({"quota": Delta("quota", -30)}, task_id="tsk_1")
        _, data, _, params = p.updates[0]
        assert isinstance(data["quota"], Delta)
        assert data["quota"].amount == -30
        assert params == ["tsk_1"]

    async def test_duplicate_on_update_is_classified(self) -> None:
        """A unique index rejects an UPDATE as loudly as an INSERT.

        Renaming a row onto a name another row already holds fails the same
        statement shape as a duplicate insert, so it has to surface as the same
        error type — otherwise the caller can only tell "that name is taken"
        from "the database is down" by matching driver text.
        """
        from quadkit.sql.exceptions import DuplicateKeyError

        repo, p = _repo()
        p.update_result = UpdateResult(
            affected_rows=0,
            execution_time=0.0,
            success=False,
            error_message="UNIQUE constraint failed: prefill_groups.name",
        )
        with pytest.raises(DuplicateKeyError):
            await repo.update_where({"name": "Taken"}, task_id="tsk_1")

    async def test_mysql_duplicate_on_update_is_classified(self) -> None:
        from quadkit.sql.exceptions import DuplicateKeyError

        repo, p = _repo()
        p.update_result = UpdateResult(
            affected_rows=0,
            execution_time=0.0,
            success=False,
            error_message="(1062, \"Duplicate entry 'Taken' for key 'uq_name'\")",
        )
        with pytest.raises(DuplicateKeyError):
            await repo.update_where({"name": "Taken"}, task_id="tsk_1")

    async def test_a_non_integrity_update_failure_stays_generic(self) -> None:
        """Only constraint violations are reclassified; an outage is an outage."""
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        p.update_result = UpdateResult(
            affected_rows=0,
            execution_time=0.0,
            success=False,
            error_message="database is locked",
        )
        with pytest.raises(RepositoryError) as caught:
            await repo.update_where({"state": "{}"}, task_id="tsk_1")
        assert "database is locked" in str(caught.value)

    async def test_zero_rows_is_an_answer_not_an_error(self) -> None:
        """A worker that lost its claim must see ``False``, not an exception."""
        repo, p = _repo()
        p.update_result = UpdateResult(
            affected_rows=0, execution_time=0.0, success=True
        )
        assert await repo.update_where({"state": "{}"}, task_id="tsk_1") == 0

    async def test_empty_data_is_refused(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        with pytest.raises(RepositoryError, match="at least one column value"):
            await repo.update_where({}, task_id="tsk_1")
        assert p.updates == []

    async def test_no_filters_is_refused(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        with pytest.raises(RepositoryError, match="at least one filter"):
            await repo.update_where({"status": "failed"})
        assert p.updates == []

    async def test_failure_raises_repository_error(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        p.update_result = UpdateResult(
            affected_rows=0, execution_time=0.0, success=False, error_message="nope"
        )
        with pytest.raises(RepositoryError, match="Update failed: nope"):
            await repo.update_where({"state": "{}"}, task_id="tsk_1")


class TestMultiColumnOrdering:
    """A tie-break is not optional when the leading column is not unique."""

    async def test_columns_and_directions_pair_up(self) -> None:
        from quadkit.sql.repositories.filter_objects import F

        repo, p = _repo()
        await repo.find_many(
            F("status").in_(("pending",)),
            sort_by=("created_at", "id"),
            sort_order="desc",
        )
        query, params = p.queries[0]
        assert 'ORDER BY "created_at" DESC, "id" DESC' in query
        assert params == ["pending"]

    async def test_one_direction_applies_to_every_column(self) -> None:
        repo, p = _repo()
        await repo.find_many(sort_by=("created_at", "id"), sort_order=("desc",))
        query, _ = p.queries[0]
        assert 'ORDER BY "created_at" DESC, "id" DESC' in query

    async def test_per_column_directions(self) -> None:
        repo, p = _repo()
        await repo.find_many(sort_by=("priority", "name"), sort_order=("asc", "desc"))
        query, _ = p.queries[0]
        assert 'ORDER BY "priority" ASC, "name" DESC' in query

    async def test_a_single_string_still_works(self) -> None:
        repo, p = _repo()
        await repo.find_many(sort_by="name")
        query, _ = p.queries[0]
        assert 'ORDER BY "name" ASC' in query

    async def test_mismatched_direction_count_is_refused(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, _ = _repo()
        with pytest.raises(RepositoryError, match="sort_order has"):
            await repo.find_many(sort_by=("a", "b"), sort_order=("asc", "desc", "asc"))

    async def test_unknown_direction_is_refused(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, _ = _repo()
        with pytest.raises(RepositoryError, match="must be 'asc' or 'desc'"):
            await repo.find_many(sort_by="name", sort_order="sideways")

    async def test_allowed_sort_fields_covers_every_column(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, _ = _repo()
        with pytest.raises(RepositoryError, match="Sorting by 'id' is not allowed"):
            await repo.find_many(
                sort_by=("created_at", "id"), allowed_sort_fields=["created_at"]
            )


class ColumnAwareProvider(RecordingProvider):
    """A provider that can report a table's columns, like the real ones can.

    `RecordingProvider` predates `get_table_columns`, so a repository over it
    resolves "unknown" and stamps both timestamps. That is the compatibility
    path; these tests cover the path a real host takes.
    """

    def __init__(self, columns: list[str] | None = None, *, fail: bool = False) -> None:
        super().__init__()
        self.columns = columns or []
        self.fail = fail
        self.probes: list[str] = []

    async def get_table_columns(self, table_name: str) -> list[dict[str, Any]]:
        self.probes.append(table_name)
        if self.fail:
            raise DatabaseError("introspection unavailable")
        return [{"name": name, "type": "TEXT"} for name in self.columns]


class TestTimestampStampFollowsSchema:
    """`create`/`upsert` stamp only the timestamp columns the table declares.

    Stamping a column that does not exist is not a harmless extra field: the
    INSERT is rejected before any row lands. A host whose settings table keeps
    `updated_at` and no `created_at` therefore cannot use `upsert` at all until
    the write path asks the schema.
    """

    async def test_create_skips_a_column_the_table_lacks(self) -> None:
        """A table with `updated_at` but no `created_at` gets only `updated_at`."""
        provider = ColumnAwareProvider(["key", "value", "updated_at"])
        repo = DictRepo(provider)

        await repo.create({"key": "a", "value": "1"})

        written = provider.inserts[0][1]
        assert "updated_at" in written
        assert "created_at" not in written

    async def test_upsert_skips_a_column_the_table_lacks(self) -> None:
        """The same rule holds for the conflict write."""
        provider = ColumnAwareProvider(["key", "value", "updated_at"])
        repo = DictRepo(provider)

        await repo.upsert({"key": "a", "value": "1"}, conflict_fields=["key"])

        query, params = provider.queries[0]
        assert "created_at" not in query
        assert '"updated_at" = EXCLUDED."updated_at"' in query
        assert all("created_at" not in str(param) for param in params)

    async def test_create_stamps_both_when_the_table_has_both(self) -> None:
        """A table carrying both columns keeps the full audit stamp."""
        provider = ColumnAwareProvider(["id", "name", "created_at", "updated_at"])
        repo = DictRepo(provider)

        await repo.create({"name": "a"})

        written = provider.inserts[0][1]
        assert "created_at" in written
        assert "updated_at" in written

    async def test_explicit_values_are_never_overwritten(self) -> None:
        """An entity that supplies its own timestamps keeps them."""
        provider = ColumnAwareProvider(["id", "created_at", "updated_at"])
        repo = DictRepo(provider)

        await repo.create({"name": "a", "created_at": "x", "updated_at": "y"})

        written = provider.inserts[0][1]
        assert (written["created_at"], written["updated_at"]) == ("x", "y")

    async def test_a_failed_probe_keeps_the_old_behaviour(self) -> None:
        """Unresolvable schema → stamp both, as every host did before."""
        provider = ColumnAwareProvider(["id"], fail=True)
        repo = DictRepo(provider)

        await repo.create({"name": "a"})

        written = provider.inserts[0][1]
        assert "created_at" in written
        assert "updated_at" in written

    async def test_a_provider_without_the_probe_keeps_the_old_behaviour(self) -> None:
        """A provider that predates `get_table_columns` is not broken by this."""
        repo, provider = _repo()

        await repo.create({"name": "a"})

        written = provider.inserts[0][1]
        assert "created_at" in written
        assert "updated_at" in written

    async def test_the_schema_is_probed_once_per_repository(self) -> None:
        """One probe, then cached — the schema cannot change under the object."""
        provider = ColumnAwareProvider(["id", "created_at", "updated_at"])
        repo = DictRepo(provider)

        await repo.create({"name": "a"})
        await repo.upsert({"name": "b"})
        await repo.create({"name": "c"})

        assert provider.probes == ["users"]


class TestUpdateTimestampFollowsSchema:
    """`update` stamps `updated_at` only when the table has the column.

    The same defect as the insert path: naming a column the table does not
    define fails the UPDATE, so a table without an audit column could not be
    updated through the framework at all.
    """

    async def test_update_skips_updated_at_when_the_table_lacks_it(self) -> None:
        provider = ColumnAwareProvider(["id", "name"])
        repo = DictRepo(provider)

        await repo.update({"id": 1, "name": "a"})

        _, data, _, _ = provider.updates[0]
        assert "updated_at" not in data
        assert data["name"] == "a"

    async def test_update_stamps_updated_at_when_present(self) -> None:
        provider = ColumnAwareProvider(["id", "name", "updated_at"])
        repo = DictRepo(provider)

        await repo.update({"id": 1, "name": "a"})

        _, data, _, _ = provider.updates[0]
        assert "updated_at" in data
