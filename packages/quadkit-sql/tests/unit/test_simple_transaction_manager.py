"""Unit tests for SimpleTransactionManager and the @transactional decorator."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.sql.exceptions import (
    DatabaseError,
    DeadlockError,
    QueryError,
)
from quadkit.sql.unit_of_work.decorators import transactional
from quadkit.sql.unit_of_work.manager import SimpleTransactionManager, transaction


class _Connection:
    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, sql: str, *args: Any) -> None:
        self.statements.append(sql)


class _Pool:
    def __init__(self) -> None:
        self.conn = _Connection()

    def get_connection(self) -> _PoolConnection:
        return _PoolConnection(self.conn)


class _PoolConnection:
    def __init__(self, conn: _Connection) -> None:
        self._conn = conn

    async def __aenter__(self) -> _Connection:
        return self._conn

    async def __aexit__(self, *exc: Any) -> None:
        return None


class TestSimpleTransactionManager:
    @pytest.mark.asyncio
    async def test_commits_on_success(self) -> None:
        pool = _Pool()
        manager = SimpleTransactionManager(pool)
        async with manager.transaction() as conn:
            assert conn is pool.conn
        assert pool.conn.statements == ["BEGIN", "COMMIT"]
        assert manager.get_current_connection() is None

    @pytest.mark.asyncio
    async def test_nested_transaction_reuses_connection(self) -> None:
        pool = _Pool()
        manager = SimpleTransactionManager(pool)
        async with manager.transaction() as outer:
            async with manager.transaction() as inner:
                assert inner is outer
        # Only one BEGIN/COMMIT pair for the whole scope.
        assert pool.conn.statements == ["BEGIN", "COMMIT"]

    @pytest.mark.asyncio
    async def test_rolls_back_on_database_error(self) -> None:
        pool = _Pool()
        manager = SimpleTransactionManager(pool)
        with pytest.raises(DatabaseError):
            async with manager.transaction():
                raise DatabaseError("boom")
        assert pool.conn.statements == ["BEGIN", "ROLLBACK"]

    @pytest.mark.asyncio
    async def test_rolls_back_on_query_error(self) -> None:
        pool = _Pool()
        manager = SimpleTransactionManager(pool)
        with pytest.raises(QueryError):
            async with transaction(manager):
                raise QueryError("bad sql")
        assert "ROLLBACK" in pool.conn.statements

    @pytest.mark.asyncio
    async def test_get_current_connection_inside_transaction(self) -> None:
        pool = _Pool()
        manager = SimpleTransactionManager(pool)
        assert manager.get_current_connection() is None

        async def peek() -> Any:
            async with manager.transaction() as conn:
                return manager.get_current_connection()

        assert await peek() is pool.conn


class _Provider:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def begin_transaction(self) -> None:
        self.calls.append("begin")

    async def commit_transaction(self) -> None:
        self.calls.append("commit")

    async def rollback_transaction(self) -> None:
        self.calls.append("rollback")


class TestTransactionalDecorator:
    @pytest.mark.asyncio
    async def test_missing_provider_raises_value_error(self) -> None:
        @transactional()
        async def op() -> None:
            return None

        with pytest.raises(ValueError, match="provider"):
            await op()

    @pytest.mark.asyncio
    async def test_success_begins_and_commits(self) -> None:
        provider = _Provider()

        @transactional(provider)
        async def op() -> str:
            return "done"

        assert await op() == "done"
        assert provider.calls == ["begin", "commit"]

    @pytest.mark.asyncio
    async def test_uses_kwarg_provider_when_not_passed_to_decorator(self) -> None:
        provider = _Provider()

        @transactional()
        async def op(provider: Any) -> None:
            return None

        await op(provider=provider)
        assert provider.calls == ["begin", "commit"]

    @pytest.mark.asyncio
    async def test_database_error_rolls_back_and_retries(self) -> None:
        provider = _Provider()

        @transactional(provider, retries=2, backoff_factor=0.0)
        async def flaky() -> str:
            if len(provider.calls) < 5:  # first two attempts fail
                raise DeadlockError("deadlock")
            return "ok"

        assert await flaky() == "ok"
        # begin/fail/rollback twice, then begin/commit.
        assert provider.calls == [
            "begin",
            "rollback",
            "begin",
            "rollback",
            "begin",
            "commit",
        ]

    @pytest.mark.asyncio
    async def test_retries_exhausted_raises_last_error(self) -> None:
        provider = _Provider()

        @transactional(provider, retries=1, backoff_factor=0.0)
        async def always_fails() -> None:
            raise DeadlockError("again")

        with pytest.raises(DeadlockError, match="again"):
            await always_fails()
        assert provider.calls.count("rollback") == 2

    @pytest.mark.asyncio
    async def test_non_retryable_error_rolls_back_without_retry(self) -> None:
        provider = _Provider()

        @transactional(provider, retries=3, backoff_factor=0.0)
        async def fails() -> None:
            raise QueryError("syntax")

        with pytest.raises(QueryError):
            await fails()
        assert provider.calls == ["begin", "rollback"]
