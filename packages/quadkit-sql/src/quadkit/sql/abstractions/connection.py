"""Database connection abstractions"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class DatabaseConnection(ABC):
    """Abstract base class for database connections"""

    @abstractmethod
    async def execute(
        self,
        query: str,
        params: tuple[object, ...] | None = None,
    ) -> Any:
        """Execute a query and return results"""

    @abstractmethod
    async def execute_many(
        self,
        query: str,
        params_list: list[tuple[object, ...]],
    ) -> None:
        """Execute a query with multiple parameter sets"""

    @abstractmethod
    async def fetch_one(
        self,
        query: str,
        params: tuple[object, ...] | None = None,
    ) -> dict[str, Any] | None:
        """Fetch a single row"""

    @abstractmethod
    async def fetch_all(
        self,
        query: str,
        params: tuple[object, ...] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all rows"""

    @abstractmethod
    async def close(self) -> None:
        """Close the connection"""

    def transaction(self) -> AbstractAsyncContextManager[Any]:
        """Return an async context manager for transactions.

        Default no-op implementation yields self which is sufficient for most
        in-memory or mocked connections used in tests. Concrete drivers may
        override to provide real transactional behavior.
        """

        @asynccontextmanager
        async def _no_op() -> AsyncGenerator[Any, None]:
            yield self

        return _no_op()
