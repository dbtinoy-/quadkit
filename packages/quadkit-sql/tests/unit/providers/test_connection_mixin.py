"""Tests for _ConnectionMixin: connection lifecycle, transactions, scope,
manual pool management, and eviction.

The mixin's ``manager`` is a *sync* facade whose individual methods may be
async, so tests use MagicMock hosts with targeted AsyncMock methods.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts import HealthStatus
from quadkit.sql.providers._connection_mixin import _ConnectionMixin


class _Health:
    def __init__(self, status: HealthStatus, error: str | None = None) -> None:
        self.status = status
        self.error = error


class _Host(_ConnectionMixin):
    """Minimal host carrying the mixin's expected attributes.

    Does NOT override ``boot`` — the mixin's real boot logic is under test.
    """

    def __init__(self, db_provider: Any = None, **attrs: Any) -> None:
        self.db_provider = db_provider
        self._started = False
        self._pipeline = None
        self.name = "db-service"
        self.kwargs: dict[str, Any] = {}
        self.connection_pool = attrs.pop("connection_pool", None)
        self.migration_manager = attrs.pop("migration_manager", None)
        self._explicit_provider_type = attrs.pop("explicit_provider_type", None)
        self.resilience_handler = attrs.pop("resilience_handler", None)
        self.config = attrs.pop("config", None)
        self.manager = attrs.pop("manager", MagicMock())
        self.query_logger = None
        self._manual_connections: dict[int, Any] = {}
        self._context = None
        self._hook_registry = None
        for k, v in attrs.items():
            setattr(self, k, v)

    async def health_check(self) -> _Health:
        return _Health(HealthStatus.HEALTHY)


class _StubBootHost(_Host):
    """Host whose boot is a stub (for connect/is_connected tests only)."""

    async def boot(self, container: Any | None = None) -> None:
        self._started = True


def _ok_provider(connect: Any = None, **extra: Any) -> AsyncMock:
    p = AsyncMock()
    p.is_connected = AsyncMock(return_value=True)
    p.connect = connect if connect is not None else AsyncMock()
    for k, v in extra.items():
        setattr(p, k, v)
    return p


def _manager(**async_methods: Any) -> MagicMock:
    """Sync-facade manager with selected async methods."""
    m = MagicMock()
    for name, mock in async_methods.items():
        setattr(m, name, mock)
    return m


def _inner_cm(result: Any = None) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=result)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


class TestConnectDisconnect:
    async def test_connect_delegates_to_provider(self) -> None:
        p = _ok_provider()
        host = _Host(db_provider=p)
        await host.connect()
        p.connect.assert_awaited_once()

    async def test_connect_without_provider_boots(self) -> None:
        host = _StubBootHost()
        await host.connect()
        assert host._started is True

    async def test_connect_no_double_boot(self) -> None:
        boots = 0

        class _H(_Host):
            async def boot(self, container: Any | None = None) -> None:
                nonlocal boots
                boots += 1
                self._started = True

        host = _H()
        await host.connect()
        await host.connect()
        assert boots == 1

    async def test_disconnect_delegates(self) -> None:
        p = _ok_provider()
        host = _Host(db_provider=p)
        await host.disconnect()
        p.disconnect.assert_awaited_once()

    async def test_is_connected_with_provider(self) -> None:
        p = _ok_provider(is_connected=AsyncMock(return_value=True))
        host = _Host(db_provider=p)
        assert await host.is_connected() is True
        p.is_connected.assert_awaited_once()

    async def test_is_connected_falls_back_to_started(self) -> None:
        host = _Host()
        assert await host.is_connected() is False
        host._started = True
        assert await host.is_connected() is True


class TestBoot:
    async def test_boot_connects_and_marks_started(self) -> None:
        p = _ok_provider()
        host = _Host(db_provider=p)
        await host.boot()
        assert host._started is True
        p.connect.assert_awaited_once()

    async def test_boot_idempotent(self) -> None:
        p = _ok_provider()
        host = _Host(db_provider=p)
        await host.boot()
        await host.boot()
        p.connect.assert_awaited_once()

    async def test_concurrent_boots_open_one_connection(self) -> None:
        connects = 0

        class _SlowProvider:
            async def connect(self) -> None:
                nonlocal connects
                connects += 1
                await asyncio.sleep(0)

            async def disconnect(self) -> None:
                return None

            async def is_connected(self) -> bool:
                return True

        host = _Host(db_provider=_SlowProvider())

        async def slow_health() -> _Health:
            await asyncio.sleep(0)
            return _Health(HealthStatus.HEALTHY)

        host.health_check = slow_health  # type: ignore[method-assign]

        await asyncio.gather(host.boot(), host.boot())

        assert connects == 1
        assert host._started is True

    async def test_boot_unhealthy_raises(self) -> None:
        host = _Host(db_provider=_ok_provider())

        async def bad_health() -> _Health:
            return _Health(HealthStatus.UNHEALTHY, error="db down")

        host.health_check = bad_health  # type: ignore[method-assign]
        with pytest.raises(RuntimeError, match="Database health check failed: db down"):
            await host.boot()
        assert host._started is False

    async def test_boot_initializes_pool_and_migrations(self) -> None:
        pool = MagicMock()
        pool._initialized = False
        pool.initialize = AsyncMock()
        mm = MagicMock()
        mm._initialized = False
        mm.initialize_migration_table = AsyncMock()
        mm.upgrade = AsyncMock()
        host = _Host(
            db_provider=_ok_provider(),
            connection_pool=pool,
            migration_manager=mm,
        )
        await host.boot()
        pool.initialize.assert_awaited_once()
        mm.initialize_migration_table.assert_awaited_once()
        mm.upgrade.assert_awaited_once_with("head")

    async def test_boot_skips_initialized_components(self) -> None:
        pool = MagicMock()
        pool._initialized = True
        pool.initialize = AsyncMock()
        mm = MagicMock()
        mm._initialized = True
        mm.initialize_migration_table = AsyncMock()
        mm.upgrade = AsyncMock()
        host = _Host(
            db_provider=_ok_provider(),
            connection_pool=pool,
            migration_manager=mm,
        )
        await host.boot()
        pool.initialize.assert_not_awaited()
        mm.initialize_migration_table.assert_not_awaited()


class TestTransactions:
    async def test_transaction_context_manager(self) -> None:
        inner = _inner_cm()
        called: list[Any] = []

        def tx(iso: Any) -> MagicMock:
            called.append(iso)
            return inner

        manager = _manager(transaction=tx)
        host = _Host(db_provider=_ok_provider(), manager=manager)
        async with host.transaction():
            pass
        inner.__aexit__.assert_awaited_once()
        assert called == [None]

    async def test_transaction_boots_when_needed(self) -> None:
        inner = _inner_cm()

        def tx2(iso: Any) -> MagicMock:
            return inner

        manager = _manager(transaction=tx2)
        host = _StubBootHost(manager=manager)
        assert host.db_provider is None
        async with host.transaction():
            pass
        assert host._started is True  # booted

    async def test_begin_commit_rollback_delegate(self) -> None:
        p = _ok_provider()
        host = _Host(db_provider=p)
        await host.begin_transaction()
        p.begin_transaction.assert_awaited_once()
        await host.commit_transaction()
        p.commit_transaction.assert_awaited_once()
        await host.rollback_transaction()
        p.rollback_transaction.assert_awaited_once()

    async def test_commit_falls_back_to_commit_method(self) -> None:
        p = _ok_provider()
        del p.commit_transaction
        p.commit = AsyncMock()
        host = _Host(db_provider=p)
        await host.commit_transaction()
        p.commit.assert_awaited_once()

    async def test_rollback_falls_back_to_rollback_method(self) -> None:
        p = _ok_provider()
        del p.rollback_transaction
        p.rollback = AsyncMock()
        host = _Host(db_provider=p)
        await host.rollback_transaction()
        p.rollback.assert_awaited_once()


class TestScoping:
    async def test_scoped_context_delegates(self) -> None:
        inner = _inner_cm({"scope": 1})
        manager = _manager(scoped_context=lambda: inner)
        host = _Host(manager=manager)
        async with host.scoped_context() as ctx:
            assert ctx == {"scope": 1}

    def test_get_current_context_delegates(self) -> None:
        manager = MagicMock()
        manager.get_current_context.return_value = {"a": 1}
        host = _Host(manager=manager)
        assert host.get_current_context() == {"a": 1}

    async def test_get_scoped_connection_boots(self) -> None:
        manager = _manager(get_connection=AsyncMock(return_value="conn"))
        host = _StubBootHost(manager=manager)
        conn = await host.get_scoped_connection()
        assert conn == "conn"
        assert host._started is True

    def test_get_unit_of_work_delegates(self) -> None:
        manager = MagicMock()
        manager.get_unit_of_work.return_value = "uow"
        host = _Host(manager=manager)
        assert host.get_unit_of_work() == "uow"


class TestGetConnection:
    async def test_borrows_scoped_connection(self) -> None:
        manager = MagicMock()
        manager.get_current_context.return_value = {"connection": "scoped"}
        manager.get_connection = AsyncMock(return_value="conn")
        host = _Host(manager=manager)
        async with host.get_connection() as conn:
            assert conn == "conn"

    async def test_pool_connection_when_started(self) -> None:
        provider_cm = _inner_cm("pool-conn")
        provider_manager = MagicMock()
        provider_manager.get_connection.return_value = provider_cm
        p = _ok_provider(connection_manager=provider_manager)
        manager = MagicMock()
        manager.get_current_context.return_value = None
        host = _Host(db_provider=p, manager=manager)
        host._started = True
        async with host.get_connection() as conn:
            assert conn == "pool-conn"
        provider_cm.__aexit__.assert_awaited_once()

    async def test_raw_connection_fallback_closes(self) -> None:
        conn = AsyncMock()
        manager = MagicMock()
        manager.get_current_context.return_value = None
        manager.get_connection = AsyncMock(return_value=conn)
        host = _Host(manager=manager)
        async with host.get_connection() as c:
            assert c is conn
        conn.close.assert_awaited_once()

    async def test_raw_connection_close_error_swallowed(self) -> None:
        conn = AsyncMock()
        conn.close.side_effect = RuntimeError("close failed")
        manager = MagicMock()
        manager.get_current_context.return_value = None
        manager.get_connection = AsyncMock(return_value=conn)
        host = _Host(manager=manager)
        async with host.get_connection():
            pass  # must not raise


class TestAcquireRelease:
    def _pool(self) -> MagicMock:
        pool = MagicMock()
        pool._initialized = False
        pool.initialize = AsyncMock()
        pool.get_connection.return_value = _inner_cm("manual-conn")
        return pool

    async def test_acquire_outside_scope_tracks_cm(self) -> None:
        pool = self._pool()
        manager = MagicMock()
        manager.get_current_context.return_value = None
        host = _Host(
            db_provider=_ok_provider(), connection_pool=pool, manager=manager
        )
        conn = await host.acquire()
        assert conn == "manual-conn"
        assert id(conn) in host._manual_connections
        pool.initialize.assert_awaited_once()

    async def test_release_returns_tracked_cm(self) -> None:
        pool = self._pool()
        manager = MagicMock()
        manager.get_current_context.return_value = None
        host = _Host(
            db_provider=_ok_provider(), connection_pool=pool, manager=manager
        )
        conn = await host.acquire()
        cm = host._manual_connections[id(conn)]
        await host.release(conn)
        assert id(conn) not in host._manual_connections
        cm.__aexit__.assert_awaited_once()

    async def test_release_delegates_when_untracked(self) -> None:
        p = _ok_provider()
        manager = MagicMock()
        host = _Host(db_provider=p, manager=manager)
        await host.release("someone-elses-conn")
        p.release.assert_awaited_once_with("someone-elses-conn")


class TestShutdown:
    async def test_shutdown_noop_when_not_started(self) -> None:
        p = _ok_provider()
        host = _Host(db_provider=p)
        await host.shutdown()  # must not raise, provider untouched
        assert host._started is False
        p.disconnect.assert_not_awaited()

    async def test_shutdown_releases_manual_connections(self) -> None:
        p = _ok_provider()
        pool = MagicMock()
        pool.shutdown = AsyncMock()
        cm = _inner_cm()
        host = _Host(db_provider=p, connection_pool=pool)
        host._started = True
        host._manual_connections[1] = cm
        await host.shutdown()
        cm.__aexit__.assert_awaited_once()
        assert host._manual_connections == {}
        pool.shutdown.assert_awaited_once()
        p.disconnect.assert_awaited_once()
        assert host._started is False


class TestUrl:
    def test_url_from_secret_str(self) -> None:
        class _Secret:
            def get_secret_value(self) -> str:
                return "postgres://u:p@h/db"

        class _Backend:
            url = _Secret()

        class _Config:
            backend = _Backend()

        host = _Host(config=_Config())
        assert host.url == "postgres://u:p@h/db"

    def test_url_from_plain_str(self) -> None:
        class _Backend:
            url = "mysql://h/db"

        class _Config:
            backend = _Backend()

        host = _Host(config=_Config())
        assert host.url == "mysql://h/db"


class TestEvictDeadConnections:
    async def test_no_pool_returns_zero(self) -> None:
        host = _Host()
        assert await host.evict_dead_connections() == 0

    async def test_pool_without_validator_returns_zero(self) -> None:
        pool = MagicMock(spec=[])  # no validate_connections attribute
        host = _Host(connection_pool=pool)
        assert await host.evict_dead_connections() == 0

    async def test_delegates_to_validator(self) -> None:
        pool = MagicMock()
        pool.validate_connections = AsyncMock(return_value=3)
        host = _Host(connection_pool=pool)
        assert await host.evict_dead_connections() == 3
        pool.validate_connections.assert_awaited_once()


class TestResiliencePipeline:
    async def test_ensure_pipeline_caches(self) -> None:
        handler = MagicMock()
        handler.get_pipeline.return_value = "pipeline"
        host = _Host(resilience_handler=handler)
        first = host._ensure_resilience_pipeline()
        second = host._ensure_resilience_pipeline()
        assert first == "pipeline"
        assert second == "pipeline"
        handler.get_pipeline.assert_called_once_with("db-service")

    async def test_boot_uses_pipeline_when_retry_configured(self) -> None:
        pipeline = MagicMock()
        pipeline.execute = AsyncMock()
        handler = MagicMock()
        handler.retry_config = {"retries": 3}
        handler.get_pipeline.return_value = pipeline
        p = _ok_provider()
        host = _Host(db_provider=p, resilience_handler=handler)
        host.kwargs["connection_retry"] = True
        await host.boot()
        pipeline.execute.assert_awaited_once()
        # When the retry pipeline is active, boot runs connect through
        # pipeline.execute; p.connect is only touched when there is no
        # pipeline.  Asserting on pipeline.execute is the meaningful check.
        assert p.connect.await_count == 0

    async def test_boot_without_retry_skips_pipeline(self) -> None:
        handler = MagicMock()
        handler.retry_config = {"retries": 3}
        p = _ok_provider()
        host = _Host(db_provider=p, resilience_handler=handler)
        host.kwargs["connection_retry"] = False
        await host.boot()
        handler.get_pipeline.assert_not_called()
        p.connect.assert_awaited_once()
