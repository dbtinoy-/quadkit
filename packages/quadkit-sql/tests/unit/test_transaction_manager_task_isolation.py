"""
P1-5: TransactionManager transaction state must be task-local.

Two concurrent async tasks sharing the same TransactionManager singleton must
never bleed _in_transaction / _transaction_connection state into each other.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import contextvars
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.sql.providers.transaction_manager import TransactionManager

# ---------------------------------------------------------------------------
# Minimal concrete subclass — satisfies abstract methods with no-ops
# ---------------------------------------------------------------------------


class _NoOpTransactionManager(TransactionManager):
    async def _begin_transaction_raw(
        self, connection: Any, isolation: Any | None = None
    ) -> None:
        pass

    async def _commit_transaction_raw(self, connection: Any) -> None:
        pass

    async def _rollback_transaction_raw(self, connection: Any) -> None:
        pass


def _make_manager() -> _NoOpTransactionManager:
    """Build a TransactionManager with a stub connection manager."""
    conn_manager = MagicMock()

    fake_conn = MagicMock()
    fake_conn.execute = AsyncMock()

    @asynccontextmanager
    async def _get_connection():
        yield fake_conn

    conn_manager.get_connection = _get_connection
    conn_manager._create_connection = AsyncMock(return_value=fake_conn)
    conn_manager._close_connection = AsyncMock()

    return _NoOpTransactionManager(conn_manager)


# ---------------------------------------------------------------------------
# Structural check — must use ContextVar after fix
# ---------------------------------------------------------------------------


def test_transaction_manager_uses_contextvars_for_state() -> None:
    """P1-5: _in_transaction_var and _transaction_connection_var must be ContextVars."""
    manager = _make_manager()

    assert hasattr(manager, "_in_transaction_var"), (
        "_in_transaction_var attribute missing — fix not applied"
    )
    assert hasattr(manager, "_transaction_connection_var"), (
        "_transaction_connection_var attribute missing — fix not applied"
    )
    assert isinstance(manager._in_transaction_var, contextvars.ContextVar), (
        "_in_transaction_var must be a contextvars.ContextVar"
    )
    assert isinstance(manager._transaction_connection_var, contextvars.ContextVar), (
        "_transaction_connection_var must be a contextvars.ContextVar"
    )


# ---------------------------------------------------------------------------
# Concurrency isolation check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transaction_manager_transaction_state_is_task_isolated() -> None:
    """P1-5: Two concurrent tasks must have independent transaction state.

    Task A enters a transaction and checks its own state while Task B (running
    concurrently on the same manager) must observe *no* active transaction.
    Without ContextVar the shared bool would leak across tasks.
    """
    manager = _make_manager()

    task_a_saw_in_transaction: bool | None = None
    task_b_saw_in_transaction: bool | None = None

    # Barrier so both tasks are alive at the same time
    barrier = asyncio.Barrier(2)

    async def task_a() -> None:
        nonlocal task_a_saw_in_transaction
        async with manager.transaction():
            # Inside the transaction — Task A must see True
            task_a_saw_in_transaction = manager.in_transaction
            # Let Task B run and read state concurrently
            await barrier.wait()

    async def task_b() -> None:
        nonlocal task_b_saw_in_transaction
        # Wait until Task A is inside its transaction, then read state
        await barrier.wait()
        # Task B is NOT in a transaction — it must see False
        task_b_saw_in_transaction = manager.in_transaction

    await asyncio.gather(task_a(), task_b())

    assert task_a_saw_in_transaction is True, (
        "Task A must see in_transaction=True inside transaction()"
    )
    assert task_b_saw_in_transaction is False, (
        "Task B must NOT see Task A's transaction state (state bled across tasks)"
    )
