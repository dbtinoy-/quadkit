"""Unit tests for UoW lifecycle hooks (on_commit / on_rollback).

Covers the unified lifecycle-hook API:

- ``AbstractUnitOfWork.on_commit`` / ``on_rollback`` run their callbacks
  after a successful commit / after a rollback, in all callback styles
  (sync, async, sync-returning-awaitable).
- ``SimpleUnitOfWork.before_commit`` / ``after_commit`` execute through
  the same runner around the actual DB operations.
- ``ScopedUnitOfWork`` gained the hooks plus the event-collection API
  (``register_event`` / ``collect_events``) that its protocol promises,
  and its context-manager exit now routes through ``commit()`` /
  ``rollback()`` so hooks run and double provider calls are guarded.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from quadkit.contracts import DatabaseProviderProtocol
from quadkit.sql.managers import ScopedUnitOfWork
from quadkit.domain.unit_of_work import AbstractUnitOfWork, run_lifecycle_hooks
from quadkit.sql.unit_of_work.simple import SimpleUnitOfWork


class _TestUOW(AbstractUnitOfWork):
    """Concrete UoW with a no-op flush."""

    async def _flush(self) -> None:
        pass


class _MockEntity:
    __table_name__ = "mock_entities"

    def __init__(self, id: int = 1, name: str = "test") -> None:
        self.id = id
        self.name = name


# ─────────────────────────────────────────────────────────────────────
# AbstractUnitOfWork hooks
# ─────────────────────────────────────────────────────────────────────


class TestAbstractUowHooks:
    @pytest.mark.asyncio
    async def test_on_commit_runs_after_successful_commit(self) -> None:
        uow = _TestUOW()
        calls: list[str] = []

        uow.on_commit(lambda: calls.append("sync"))

        async def async_hook() -> None:
            calls.append("async")

        uow.on_commit(async_hook)

        def returning_coroutine() -> Any:
            return async_hook()

        uow.on_commit(returning_coroutine)

        await uow.commit()

        assert calls == ["sync", "async", "async"]

    @pytest.mark.asyncio
    async def test_on_commit_does_not_run_on_rollback(self) -> None:
        uow = _TestUOW()
        ran: list[str] = []
        uow.on_commit(lambda: ran.append("commit"))
        uow.on_rollback(lambda: ran.append("rollback"))

        await uow.rollback()

        assert ran == ["rollback"]

    @pytest.mark.asyncio
    async def test_on_rollback_runs_after_rollback(self) -> None:
        uow = _TestUOW()
        ran: list[str] = []
        uow.on_rollback(lambda: ran.append("sync"))

        async def async_hook() -> None:
            ran.append("async")

        uow.on_rollback(async_hook)
        await uow.rollback()

        assert ran == ["sync", "async"]

    @pytest.mark.asyncio
    async def test_hooks_run_in_registration_order(self) -> None:
        uow = _TestUOW()
        ran: list[str] = []
        for label in ("first", "second", "third"):
            uow.on_commit((lambda l=label: ran.append(l)))

        await uow.commit()

        assert ran == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_run_lifecycle_hooks_handles_all_callback_styles(self) -> None:
        ran: list[str] = []

        async def async_hook() -> None:
            ran.append("async")

        hooks: list[Any] = [
            lambda: ran.append("sync"),
            async_hook,
            lambda: async_hook(),  # sync fn returning an awaitable
            lambda: None,
        ]
        await run_lifecycle_hooks(hooks)

        assert ran == ["sync", "async", "async"]


# ─────────────────────────────────────────────────────────────────────
# SimpleUnitOfWork before/after commit hooks
# ─────────────────────────────────────────────────────────────────────


class TestSimpleUowHooks:
    @pytest.fixture
    def mock_provider(self) -> Mock:
        provider = Mock(spec=DatabaseProviderProtocol)
        provider.begin_transaction = AsyncMock()
        provider.commit_transaction = AsyncMock()
        provider.rollback_transaction = AsyncMock()
        provider.execute_insert = AsyncMock()
        provider.execute_update = AsyncMock()
        provider.execute_delete = AsyncMock()
        return provider

    @pytest.mark.asyncio
    async def test_hooks_bracket_the_db_operations(
        self, mock_provider: Mock
    ) -> None:
        uow = SimpleUnitOfWork(mock_provider)
        order: list[str] = []

        uow.before_commit(lambda: order.append("before"))

        async def after() -> None:
            order.append("after")

        uow.after_commit(after)

        async with uow:
            uow.register_new(_MockEntity(id=1))

        assert order == ["before", "after"]
        mock_provider.commit_transaction.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_after_commit_does_not_run_when_flush_fails(
        self, mock_provider: Mock
    ) -> None:
        from quadkit.sql.exceptions import DatabaseError

        mock_provider.commit_transaction.side_effect = DatabaseError("boom")
        uow = SimpleUnitOfWork(mock_provider)
        after_ran: list[str] = []
        uow.after_commit(lambda: after_ran.append("after"))

        with pytest.raises(DatabaseError):
            async with uow:
                uow.register_new(_MockEntity(id=1))

        assert after_ran == []
        mock_provider.rollback_transaction.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sync_hook_returning_coroutine_is_awaited(
        self, mock_provider: Mock
    ) -> None:
        uow = SimpleUnitOfWork(mock_provider)
        ran: list[str] = []

        async def inner() -> None:
            ran.append("awaited")

        uow.before_commit(lambda: inner())

        async with uow:
            pass

        assert ran == ["awaited"]


# ─────────────────────────────────────────────────────────────────────
# ScopedUnitOfWork hooks + event collection + exit-path guards
# ─────────────────────────────────────────────────────────────────────


class TestScopedUowHooks:
    @pytest.fixture
    def mock_manager(self) -> Mock:
        provider = Mock()
        provider.db_provider = Mock()
        provider.db_provider.begin_transaction = AsyncMock()
        provider.db_provider.commit = AsyncMock()
        provider.db_provider.rollback = AsyncMock()
        manager = Mock()
        manager.provider = provider
        manager.manager = None
        manager.get_current_context = Mock(return_value={"transaction_level": 0})
        return manager

    def _uow(self, manager: Mock) -> ScopedUnitOfWork:
        return ScopedUnitOfWork(manager)

    @pytest.mark.asyncio
    async def test_collect_events_returns_and_commit_clears(
        self, mock_manager: Mock
    ) -> None:
        uow = self._uow(mock_manager)
        uow.register_event("evt-1")
        uow.register_event("evt-2")

        assert uow.collect_events() == ["evt-1", "evt-2"]
        # collect_events must not clear; commit does.
        assert uow.collect_events() == ["evt-1", "evt-2"]

        await uow.commit()
        assert uow.collect_events() == []

    @pytest.mark.asyncio
    async def test_commit_hooks_run_on_context_manager_exit(
        self, mock_manager: Mock
    ) -> None:
        uow = self._uow(mock_manager)
        ran: list[str] = []
        uow.on_commit(lambda: ran.append("commit"))

        async with uow:
            pass

        assert ran == ["commit"]
        mock_manager.provider.db_provider.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rollback_hooks_run_on_exception_exit(
        self, mock_manager: Mock
    ) -> None:
        uow = self._uow(mock_manager)
        ran: list[str] = []
        uow.on_rollback(lambda: ran.append("rollback"))

        with pytest.raises(RuntimeError, match="boom"):
            async with uow:
                raise RuntimeError("boom")

        assert ran == ["rollback"]
        mock_manager.provider.db_provider.rollback.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_explicit_commit_then_exit_does_not_double_commit(
        self, mock_manager: Mock
    ) -> None:
        uow = self._uow(mock_manager)
        ran: list[str] = []
        uow.on_commit(lambda: ran.append("commit"))

        async with uow:
            await uow.commit()

        # The exit path must be a guarded no-op: one provider commit,
        # one hook run.
        mock_manager.provider.db_provider.commit.assert_awaited_once()
        assert ran == ["commit"]

    @pytest.mark.asyncio
    async def test_rollback_after_commit_is_a_noop(self, mock_manager: Mock) -> None:
        uow = self._uow(mock_manager)
        rollback_ran: list[str] = []
        uow.on_rollback(lambda: rollback_ran.append("rollback"))

        with pytest.raises(RuntimeError, match="post-commit"):
            async with uow:
                await uow.commit()
                raise RuntimeError("post-commit")

        # The transaction is already committed; the exit must not roll
        # back the provider or fire rollback hooks.
        mock_manager.provider.db_provider.rollback.assert_not_awaited()
        assert rollback_ran == []
