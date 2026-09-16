"""Connection protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.data.sql.database._results import QueryResult


@runtime_checkable
class ConnectionProtocol(Protocol):
    """Protocol for database connections.

    Represents an active database connection that can execute queries.
    """

    async def execute(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> QueryResult:
        """Execute a SQL query.

        Args:
            query: SQL query string with positional parameters ($1, $2, ...).
            *args: Positional arguments for the query.
            timeout: Optional timeout in seconds.

        Returns:
            QueryResult with rows and metadata.
        """
        ...

    async def fetchrow(
        self,
        query: str,
        *args: Any,
        timeout: float | None = None,
    ) -> dict[str, Any] | None:
        """Fetch a single row from the database.

        Args:
            query: SQL query string.
            *args: Positional arguments for the query.
            timeout: Optional timeout in seconds.

        Returns:
            Row dictionary or None if not found.
        """
        ...

    async def close(self) -> None:
        """Close the connection."""
        ...

    async def fetch(
        self,
        query: str,
        *args: Any,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Fetch rows from the database.

        Args:
            query: SQL query string.
            *args: Positional query parameters.
            **kwargs: Named query parameters.

        Returns:
            List of row dictionaries.
        """
        ...
