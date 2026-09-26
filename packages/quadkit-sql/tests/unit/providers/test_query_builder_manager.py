"""Tests for the provider query-builder manager (dialect registry + managed builders)."""

from __future__ import annotations

from quadkit.contracts.data.sql.sql_dialect import SQLDialect
from quadkit.sql.providers.query_builder_manager import (
    MySQLDialectHandler,
    PostgresDialectHandler,
    QueryBuilderManager,
    SQLDialectRegistry,
    SQLiteDialectHandler,
)


class _CrudOps:
    def __init__(self) -> None:
        self.executed: list[tuple[str, list]] = []

    async def execute(self, sql: str, params: list) -> object:
        self.executed.append((sql, params))
        return "done"


class TestDialectHandlers:
    def test_postgres_handler(self) -> None:
        assert PostgresDialectHandler().get_dialect() == SQLDialect.POSTGRESQL

    def test_sqlite_handler(self) -> None:
        assert SQLiteDialectHandler().get_dialect() == SQLDialect.SQLITE

    def test_mysql_handler(self) -> None:
        assert MySQLDialectHandler().get_dialect() == SQLDialect.MYSQL


class TestDialectRegistry:
    def test_with_defaults_resolves(self) -> None:
        registry = SQLDialectRegistry.with_defaults()
        assert registry.get_dialect("postgresql") == SQLDialect.POSTGRESQL
        assert registry.get_dialect("postgres") == SQLDialect.POSTGRESQL
        assert registry.get_dialect("sqlite") == SQLDialect.SQLITE
        assert registry.get_dialect("mysql") == SQLDialect.MYSQL

    def test_unknown_defaults_to_postgres(self) -> None:
        registry = SQLDialectRegistry.with_defaults()
        assert registry.get_dialect("cockroachdb") == SQLDialect.POSTGRESQL

    def test_empty_registry_defaults_to_postgres(self) -> None:
        assert SQLDialectRegistry().get_dialect("anything") == SQLDialect.POSTGRESQL

    def test_register_custom_handler(self) -> None:
        class _Handler:
            def get_dialect(self) -> SQLDialect:
                return SQLDialect.MYSQL

        registry = SQLDialectRegistry()
        registry.register_handler("custom", _Handler())
        assert registry.get_dialect("custom") == SQLDialect.MYSQL

    def test_register_overrides(self) -> None:
        registry = SQLDialectRegistry.with_defaults()
        registry.register_handler("sqlite", MySQLDialectHandler())
        assert registry.get_dialect("sqlite") == SQLDialect.MYSQL


class TestQueryBuilderManager:
    def _manager(self, database_type: str | None = None) -> QueryBuilderManager:
        manager = QueryBuilderManager(_CrudOps())
        if database_type is not None:
            manager.database_type = database_type  # type: ignore[attr-defined]
        return manager

    def test_query_returns_select_builder(self) -> None:
        builder = self._manager().query("users")
        sql = builder.build().sql
        assert sql.startswith("SELECT")

    def test_insert_builder_mode(self) -> None:
        builder = self._manager().insert("users", {"name": "a"})
        sql = builder.build().sql
        assert sql.startswith("INSERT INTO")
        assert "name" in sql

    def test_update_builder_mode_requires_where(self) -> None:
        import pytest

        from quadkit.sql.query.operators import Operator

        builder = self._manager().update("users", {"name": "b"})
        with pytest.raises(ValueError, match="WHERE"):
            builder.build()
        builder.where("id", Operator.EQ, 1)
        sql = builder.build().sql
        assert sql.startswith("UPDATE")
        assert "name" in sql
        assert "WHERE" in sql

    def test_delete_builder_mode_requires_where(self) -> None:
        import pytest

        builder = self._manager().delete("users")
        with pytest.raises(ValueError, match="WHERE"):
            builder.build()
        builder.where("id", "=", 1)
        sql = builder.build().sql
        assert sql.startswith("DELETE FROM")

    def test_builder_carries_provider_reference(self) -> None:
        manager = self._manager()
        builder = manager.query("users")
        assert builder.provider is manager

    def test_dialect_from_database_type(self) -> None:
        assert self._manager("sqlite")._get_dialect() == SQLDialect.SQLITE  # noqa: SLF001
        assert self._manager("mysql")._get_dialect() == SQLDialect.MYSQL  # noqa: SLF001
        assert self._manager("postgres")._get_dialect() == SQLDialect.POSTGRESQL  # noqa: SLF001

    def test_dialect_fallback_when_attribute_missing(self) -> None:
        manager = self._manager()
        assert not hasattr(manager, "database_type")
        assert manager._get_dialect() == SQLDialect.SQLITE  # noqa: SLF001


class TestManagedExecution:
    async def test_execute_without_conn_uses_provider(self) -> None:
        crud = _CrudOps()
        manager = QueryBuilderManager(crud)
        builder = manager.query("users")
        result = await builder.execute()
        assert result == "done"
        assert len(crud.executed) == 1
        sql, params = crud.executed[0]
        assert "users" in sql
        assert isinstance(params, list)

    async def test_execute_with_conn_uses_driver(self) -> None:
        crud = _CrudOps()
        manager = QueryBuilderManager(crud)
        builder = manager.query("users").where("id", "=", 7)
        calls: list[tuple[str, object]] = []

        class _Conn:
            async def fetch(self, sql: str, *params: object) -> list:
                calls.append((sql, params))
                return []

            async def execute(self, sql: str, *params: object) -> str:
                calls.append((sql, params))
                return "OK"

        await builder.execute(_Conn())
        assert len(calls) == 1
        sql, params = calls[0]
        assert "$1" in sql  # driver-style parameter placeholder
        assert params == (7,)

    async def test_insert_execute_via_provider(self) -> None:
        crud = _CrudOps()
        manager = QueryBuilderManager(crud)
        builder = manager.insert("users", {"name": "a", "age": 3})
        await builder.execute()
        sql, params = crud.executed[0]
        assert sql.startswith("INSERT INTO")
        assert params == ["a", 3]

    async def test_where_chaining_on_managed_builder(self) -> None:
        crud = _CrudOps()
        manager = QueryBuilderManager(crud)
        builder = manager.query("users").where("status", "=", "active")
        await builder.execute()
        sql, params = crud.executed[0]
        assert "WHERE" in sql
        assert params == ["active"]
