"""Protocol definitions for quadkit-sql API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, Self, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractAsyncContextManager
    import types

    from quadkit.contracts import ContainerResolverProtocol, HealthCheckResult


@runtime_checkable
class ConnectionProtocol(Protocol):
    """Protocol for database connections.

    Mirrors ``quadkit.sql.abstractions.connection.DatabaseConnection``:
    ``execute`` / ``execute_many`` return the driver cursor/result and
    ``fetch_one`` / ``fetch_all`` return normalised ``dict`` rows.
    """

    async def execute(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
    ) -> Any:  # pragma: no cover - interface
        ...

    async def execute_many(
        self,
        sql: str,
        params_list: list[tuple[object, ...]],
    ) -> None:  # pragma: no cover - interface
        ...

    async def fetch_one(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
    ) -> dict[str, Any] | None:  # pragma: no cover - interface
        ...

    async def fetch_all(
        self,
        sql: str,
        params: tuple[object, ...] | None = None,
    ) -> list[dict[str, Any]]:  # pragma: no cover - interface
        ...

    async def close(self) -> None:  # pragma: no cover - interface
        ...


class UnitOfWorkProtocol(Protocol):
    """Protocol for Unit of Work implementations.

    Mirrors :class:`quadkit.contracts.data.sql.unit_of_work.UnitOfWorkProtocol`
    (the canonical framework protocol).
    """

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    def on_commit(
        self, callback: Callable[[], Any]
    ) -> None:  # pragma: no cover - interface
        ...

    def on_rollback(
        self, callback: Callable[[], Any]
    ) -> None:  # pragma: no cover - interface
        ...

    def register_new(self, entity: Any) -> None:  # pragma: no cover - interface
        ...

    def register_dirty(self, entity: Any) -> None:  # pragma: no cover - interface
        ...

    def register_deleted(self, entity: Any) -> None:  # pragma: no cover - interface
        ...

    def register_event(self, event: Any) -> None:  # pragma: no cover - interface
        ...

    def collect_events(self) -> list[Any]:  # pragma: no cover - interface
        ...


class DatabaseProviderProtocol(Protocol):
    """Protocol for database provider implementations.

    Attributes:
        url: The plain (decrypted) connection URL string. When the underlying
            configuration stores the URL as a ``SecretStr``, this attribute
            must return the unwrapped value — never the ``SecretStr`` wrapper.
    """

    url: str  # Plain decrypted connection URL (not a SecretStr)

    async def register(self, container: Any) -> None:  # pragma: no cover - interface
        ...

    async def boot(
        self, container: ContainerResolverProtocol
    ) -> None:  # pragma: no cover - interface
        ...

    async def shutdown(self) -> None:  # pragma: no cover - interface
        ...

    async def health_check(
        self, timeout: float = 5.0
    ) -> HealthCheckResult:  # pragma: no cover - interface
        ...

    def get_connection(
        self,
    ) -> AbstractAsyncContextManager[
        ConnectionProtocol
    ]:  # pragma: no cover - interface
        """Return an async context manager yielding a database connection.

        Implementations should provide an asynccontextmanager-compatible method
        that yields a ConnectionProtocol instance.
        """
        ...

    async def get_scoped_connection(
        self,
    ) -> ConnectionProtocol:  # pragma: no cover - interface
        ...

    def get_unit_of_work(self) -> UnitOfWorkProtocol:  # pragma: no cover - interface
        ...


__all__ = [
    "ConnectionProtocol",
    "DatabaseProviderProtocol",
    "UnitOfWorkProtocol",
]
