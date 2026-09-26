"""Focused runtime hook tests for quadkit-sql."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from quadkit.contracts.core import HookRegistryProtocol
from quadkit.sql.di.provider import DatabaseProvider
from quadkit.sql.hooks import (
    SQLConnectionReadyHook,
    SQLTransactionBegunHook,
    SQLTransactionEndedHook,
)
from quadkit.sql.providers import DatabaseService
from quadkit.sql.providers.base_provider import DatabaseDriver


class _RecordingHooks:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def register_action(
        self,
        hook_name: str,
        handler: Any,
        priority: int = 100,
        *,
        once: bool = False,
    ) -> None:
        raise NotImplementedError

    def register_filter(
        self,
        hook_name: str,
        handler: Any,
        priority: int = 100,
        *,
        once: bool = False,
    ) -> None:
        raise NotImplementedError

    def unregister_action(self, hook_name: str, handler: Any) -> bool:
        raise NotImplementedError

    def unregister_filter(self, hook_name: str, handler: Any) -> bool:
        raise NotImplementedError

    async def call_action(self, hook_name: str, **kwargs: Any) -> None:
        self.calls.append((hook_name, kwargs["payload"]))

    async def apply_filter(self, hook_name: str, value: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    def has_action(self, hook_name: str) -> bool:
        raise NotImplementedError

    def has_filter(self, hook_name: str) -> bool:
        raise NotImplementedError

    def clear(self, hook_name: str | None = None) -> None:
        raise NotImplementedError


class _HookTestProvider(DatabaseDriver):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._connections_created: list[Any] = []
        self._connections_closed: list[Any] = []
        self.commits: int = 0
        self.rollbacks: int = 0
        self.begins: int = 0

    async def _create_connection(self) -> Any:
        connection = MagicMock()
        connection.execute = AsyncMock()
        self._connections_created.append(connection)
        return connection

    async def _close_connection(self, connection: Any) -> None:
        self._connections_closed.append(connection)

    async def _execute_query_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def _execute_modify_raw(
        self,
        connection: Any,
        sql: str,
        params: list[Any] | None = None,
    ) -> int:
        return 1

    async def _begin_transaction_raw(
        self,
        connection: Any,
        isolation: Any | None = None,
    ) -> None:
        self.begins += 1

    async def _commit_transaction_raw(self, connection: Any) -> None:
        self.commits += 1

    async def _rollback_transaction_raw(self, connection: Any) -> None:
        self.rollbacks += 1

    async def _get_last_insert_id(self, connection: Any, table: str) -> Any | None:
        return None


def _payloads_for(hooks: _RecordingHooks, hook_name: str) -> list[object]:
    return [payload for name, payload in hooks.calls if name == hook_name]


@pytest.mark.asyncio
async def test_database_service_get_connection_emits_connection_acquired_hook() -> None:
    hooks = _RecordingHooks()
    provider = DatabaseService("sqlite+aiosqlite:///test.db")
    provider.set_hook_registry(hooks)

    connection = MagicMock()
    connection.close = AsyncMock()

    mock_db_provider = MagicMock()
    mock_db_provider.database_type = "sqlite"
    mock_db_provider._create_connection = AsyncMock(return_value=connection)
    mock_db_provider._close_connection = AsyncMock()
    provider.db_provider = mock_db_provider

    async with provider.get_connection() as acquired:
        assert acquired is connection

    assert _payloads_for(hooks, "connection.acquired") == [
        SQLConnectionReadyHook(backend="sqlite")
    ]


@pytest.mark.asyncio
async def test_transaction_context_emits_begin_and_end_hooks_on_commit() -> None:
    hooks = _RecordingHooks()
    provider = _HookTestProvider("sqlite:///test.db")
    provider.connection_manager.set_hook_registry(hooks)
    provider.transaction_manager.set_hook_registry(hooks)

    async with provider.transaction():
        pass

    assert _payloads_for(hooks, "transaction.begin") == [SQLTransactionBegunHook()]
    assert _payloads_for(hooks, "transaction.end") == [
        SQLTransactionEndedHook(committed=True)
    ]


@pytest.mark.asyncio
async def test_transaction_context_emits_begin_and_end_hooks_on_rollback() -> None:
    hooks = _RecordingHooks()
    provider = _HookTestProvider("sqlite:///test.db")
    provider.connection_manager.set_hook_registry(hooks)
    provider.transaction_manager.set_hook_registry(hooks)

    with pytest.raises(RuntimeError, match="boom"):
        async with provider.transaction():
            raise RuntimeError("boom")

    assert _payloads_for(hooks, "transaction.begin") == [SQLTransactionBegunHook()]
    assert _payloads_for(hooks, "transaction.end") == [
        SQLTransactionEndedHook(committed=False)
    ]


@pytest.mark.asyncio
async def test_manual_transaction_methods_do_not_emit_duplicate_begin_or_end() -> None:
    hooks = _RecordingHooks()
    provider = _HookTestProvider("sqlite:///test.db")
    provider.connection_manager.set_hook_registry(hooks)
    provider.transaction_manager.set_hook_registry(hooks)

    await provider.begin_transaction()
    await provider.begin_transaction()
    await provider.commit_transaction()
    await provider.commit_transaction()

    assert _payloads_for(hooks, "transaction.begin") == [SQLTransactionBegunHook()]
    assert _payloads_for(hooks, "transaction.end") == [
        SQLTransactionEndedHook(committed=True)
    ]


@pytest.mark.asyncio
async def test_database_service_manual_begin_transaction_emits_connection_and_transaction_hooks() -> None:
    hooks = _RecordingHooks()
    service = DatabaseService("sqlite:///test.db")
    driver = _HookTestProvider("sqlite:///test.db")
    service.db_provider = driver
    service.set_hook_registry(hooks)

    await service.begin_transaction()
    await service.commit_transaction()

    assert _payloads_for(hooks, "connection.acquired") == [
        SQLConnectionReadyHook(backend="sqlite")
    ]
    assert _payloads_for(hooks, "transaction.begin") == [SQLTransactionBegunHook()]
    assert _payloads_for(hooks, "transaction.end") == [
        SQLTransactionEndedHook(committed=True)
    ]


class _ContainerWithOptionalHooks:
    def __init__(self, hooks: HookRegistryProtocol | None) -> None:
        self._hooks = hooks

    async def resolve_optional(self, protocol: type[object]) -> object | None:
        if protocol is HookRegistryProtocol:
            return self._hooks
        return None

    async def resolve(self, protocol: type[object]) -> object | None:
        return None


@pytest.mark.asyncio
async def test_database_provider_boot_wires_optional_hook_registry_before_boot() -> (
    None
):
    hooks = _RecordingHooks()
    provider = DatabaseProvider("sqlite:///:memory:")

    boot_order: list[str] = []

    async def _boot() -> None:
        boot_order.append("boot")

    db_service = Mock()
    db_service.set_hook_registry = Mock(
        side_effect=lambda _registry: boot_order.append("set")
    )
    db_service.boot = AsyncMock(side_effect=_boot)
    db_service.metrics = None
    db_service.tracer = None
    db_service.resilience_handler = Mock()
    db_service.resilience_handler._pipeline_factory = None

    provider._db_provider = db_service

    with patch.object(provider, "_boot_admin_widgets", AsyncMock()):
        await provider.boot(_ContainerWithOptionalHooks(hooks))

    db_service.set_hook_registry.assert_called_once_with(hooks)
    db_service.boot.assert_awaited_once()
    assert boot_order[:2] == ["set", "boot"]
