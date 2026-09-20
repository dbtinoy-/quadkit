from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from quadkit.di.container import Container
from quadkit.di.provider import Provider
from quadkit.di.types import ProviderPriority


class MockProvider(Provider):
    """Base class for mock providers in testing."""

    name: str = "mock"
    priority: ProviderPriority = ProviderPriority.DOMAIN

    def __init__(self) -> None:
        super().__init__()
        self._started = False
        self._stopped = False

    async def register(self, container: Container) -> None:  # type: ignore[override]
        """No-op register for mock providers."""

    async def boot(self, container: Container) -> None:  # type: ignore[override]
        self._started = True

    async def shutdown(self) -> None:
        self._stopped = True

    @property
    def started(self) -> bool:
        return self._started

    @property
    def stopped(self) -> bool:
        return self._stopped


class MockDatabaseProvider(MockProvider):
    """Mock provider satisfying :class:`~quadkit.contracts.DatabaseProviderProtocol`.

    All query methods return neutral, empty test values so unit tests can
    resolve the database protocol without any real connection.
    """

    name: str = "mock-database"

    async def connect(self) -> None:
        """No-op connect."""

    async def disconnect(self) -> None:
        """No-op disconnect."""

    async def is_connected(self) -> bool:
        """Report connected (mock)."""
        return True

    def get_primary_pool(self) -> Any:
        """Return the (mock) primary pool — ``None`` for test doubles."""
        return None

    async def execute_query(self, *args: Any, **kwargs: Any) -> list[Any]:
        """Return an empty result set."""
        return []

    async def execute_insert(self, *args: Any, **kwargs: Any) -> int:
        """Return zero affected rows."""
        return 0

    async def execute_update(self, *args: Any, **kwargs: Any) -> int:
        """Return zero affected rows."""
        return 0

    async def execute_delete(self, *args: Any, **kwargs: Any) -> int:
        """Return zero affected rows."""
        return 0

    async def execute(self, *args: Any, **kwargs: Any) -> list[Any]:
        """Return an empty result set."""
        return []

    @asynccontextmanager
    async def transaction(self, *args: Any, **kwargs: Any) -> AsyncIterator[None]:
        """No-op transaction scope."""
        yield

    async def begin_transaction(self) -> None:
        """No-op."""

    async def commit_transaction(self) -> None:
        """No-op."""

    async def rollback_transaction(self) -> None:
        """No-op."""

    async def table_exists(self, *args: Any, **kwargs: Any) -> bool:
        """Report no tables."""
        return False

    @asynccontextmanager
    async def scoped_context(self, *args: Any, **kwargs: Any) -> AsyncIterator[None]:
        """No-op scoped context."""
        yield

    def get_scoped_connection(self) -> Any:
        """Return ``None`` (mock)."""
        return None

    def acquire(self) -> Any:
        """Return ``None`` (mock connection)."""
        return None

    def release(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""


class MockAuthProvider(MockProvider):
    """Mock provider satisfying :class:`~quadkit.contracts.AuthProviderProtocol`."""

    name: str = "mock-auth"

    async def get_user(self, *args: Any, **kwargs: Any) -> Any:
        """Return no user."""
        return None

    async def verify_token(self, *args: Any, **kwargs: Any) -> bool:
        """Report invalid tokens."""
        return False

    async def has_any_role(self, *args: Any, **kwargs: Any) -> bool:
        """Report no roles."""
        return False

    async def has_any_permission(self, *args: Any, **kwargs: Any) -> bool:
        """Report no permissions."""
        return False

    @property
    def user_store(self) -> Any:
        return None

    @property
    def session_manager(self) -> Any:
        return None

    @property
    def delegation_manager(self) -> Any:
        return None

    @property
    def api_key_manager(self) -> Any:
        return None

    @property
    def mfa_manager(self) -> Any:
        return None


class MockTaskProvider(MockProvider):
    """Mock provider satisfying :class:`~quadkit.contracts.TaskProviderProtocol`."""

    name: str = "mock-task"

    def register_handler(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""

    def register_scheduled_task(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""

    def enqueue_job(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""

    def build_idempotency_manager(self, *args: Any, **kwargs: Any) -> Any:
        """Return ``None`` (mock)."""
        return None

    def build_idempotent_task_manager(self, *args: Any, **kwargs: Any) -> Any:
        """Return ``None`` (mock)."""
        return None

    def schedule_job(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""

    def unschedule_job(self, *args: Any, **kwargs: Any) -> None:
        """No-op."""

    def get_worker_stats(self) -> dict[str, Any]:
        """Return empty stats."""
        return {}

    def get_scheduled_jobs(self) -> list[Any]:
        """Return no jobs."""
        return []


__all__ = [
    "MockAuthProvider",
    "MockDatabaseProvider",
    "MockProvider",
    "MockTaskProvider",
]
