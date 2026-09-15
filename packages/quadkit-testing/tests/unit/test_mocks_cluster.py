"""Tests for the mocks cluster: mock providers and lifecycle tracker.

Covers :mod:`quadkit.testing.mocks.base` (MockProvider and its
database/auth/task specialisations) and
:mod:`quadkit.testing.mocks.test_provider` (LifecycleTracker).
"""

from __future__ import annotations

from quadkit.di.container import Container
from quadkit.testing.mocks.base import (
    MockAuthProvider,
    MockDatabaseProvider,
    MockProvider,
    MockTaskProvider,
)
from quadkit.testing.mocks.test_provider import LifecycleTracker


# ---------------------------------------------------------------------------
# MockProvider lifecycle
# ---------------------------------------------------------------------------


async def test_mock_provider_lifecycle() -> None:
    provider = MockProvider()
    assert provider.name == "mock"
    assert provider.started is False
    assert provider.stopped is False

    container = Container()
    await provider.register(container)
    await provider.boot(container)
    assert provider.started is True

    await provider.shutdown()
    assert provider.stopped is True


# ---------------------------------------------------------------------------
# MockDatabaseProvider
# ---------------------------------------------------------------------------


async def test_mock_database_provider_neutral_values() -> None:
    db = MockDatabaseProvider()
    assert db.name == "mock-database"

    await db.connect()
    await db.disconnect()
    assert await db.is_connected() is True
    assert db.get_primary_pool() is None

    assert await db.execute_query("SELECT 1") == []
    assert await db.execute_insert("INSERT ...") == 0
    assert await db.execute_update("UPDATE ...") == 0
    assert await db.execute_delete("DELETE ...") == 0
    assert await db.execute("SELECT 1") == []

    async with db.transaction():
        pass
    await db.begin_transaction()
    await db.commit_transaction()
    await db.rollback_transaction()

    assert await db.table_exists("t") is False

    async with db.scoped_context():
        pass
    assert db.get_scoped_connection() is None
    assert db.acquire() is None
    db.release()


# ---------------------------------------------------------------------------
# MockAuthProvider
# ---------------------------------------------------------------------------


async def test_mock_auth_provider_neutral_values() -> None:
    auth = MockAuthProvider()
    assert auth.name == "mock-auth"

    assert await auth.get_user("u-1") is None
    assert await auth.verify_token("t") is False
    assert await auth.has_any_role("admin") is False
    assert await auth.has_any_permission("read") is False

    assert auth.user_store is None
    assert auth.session_manager is None
    assert auth.delegation_manager is None
    assert auth.api_key_manager is None
    assert auth.mfa_manager is None


# ---------------------------------------------------------------------------
# MockTaskProvider
# ---------------------------------------------------------------------------


async def test_mock_task_provider_neutral_values() -> None:
    tasks = MockTaskProvider()
    assert tasks.name == "mock-task"

    tasks.register_handler("job", None)
    tasks.register_scheduled_task("daily", "0 0 * * *")
    tasks.enqueue_job("job")
    assert tasks.build_idempotency_manager() is None
    assert tasks.build_idempotent_task_manager() is None
    tasks.schedule_job("job", "0 0 * * *")
    tasks.unschedule_job("job")
    assert tasks.get_worker_stats() == {}
    assert tasks.get_scheduled_jobs() == []


# ---------------------------------------------------------------------------
# LifecycleTracker
# ---------------------------------------------------------------------------


async def test_lifecycle_tracker_records_calls() -> None:
    provider = LifecycleTracker(name="svc")
    assert provider.name == "svc"
    assert provider.register_called is False
    assert provider.boot_called is False
    assert provider.shutdown_called is False

    container = Container()
    await provider.register(container)
    assert provider.register_called is True

    await provider.boot(container)
    assert provider.boot_called is True

    await provider.shutdown()
    assert provider.shutdown_called is True
