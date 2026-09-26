"""Query bus implementation.

The QueryBusProtocol dispatches queries to their handlers and supports:
- Single handler per query (enforced)
- Middleware pipeline (caching, logging)
- Explicit handler registration (no service locator)
"""

from __future__ import annotations

import contextlib
from typing import Any, TypeVar

from quadkit.contracts.exceptions.domain import DomainError
from quadkit.events.buses.base import Bus
from quadkit.events.exceptions import HandlerNotFoundError, QueryExecutionError
from quadkit.events.messages.query import Query
from quadkit.logging import get_logger

logger = get_logger(__name__)


TResult = TypeVar("TResult")


from quadkit.contracts import QueryBusProtocol as QueryBusProtocol


class QueryBusImpl(Bus[Query, Any], QueryBusProtocol):
    """Query bus for dispatching queries.

    Handlers are registered explicitly via ``register()`` or through
    ``HandlerRegistry.register_with_buses()`` during provider registration.

    Example::

        # Queries are automatically routed to handlers
        orders = await bus.execute(GetOrdersByCustomerQuery(
            customer_id="cust-123",
            status="pending"
        ))
    """

    def __init__(
        self,
        middlewares: list[Any] | None = None,
        config: Any | None = None,
    ) -> None:
        """Initialize the query bus."""
        super().__init__(middlewares)
        self._config = config

    async def execute(self, query: Query[TResult]) -> TResult:
        """Execute a query.

        Args:
            query: The query to execute.

        Returns:
            Query result.

        Raises:
            HandlerNotFoundError: If no handler is registered.
            QueryExecutionError: If query execution fails.
        """
        query_type = type(query)

        try:
            handler = await self._resolve_handler(query_type)
        except HandlerNotFoundError as e:
            raise HandlerNotFoundError("Query", query_type.__name__) from e

        from typing import cast

        try:
            return cast("TResult", await self._execute_pipeline(query, handler))
        except Exception as e:  # noqa: BLE001 — the contract is: any execution failure becomes QueryExecutionError
            # See CommandBusImpl: domain errors are caller outcomes and must
            # survive for the web exception filter to map them to a status.
            if isinstance(e, (HandlerNotFoundError, QueryExecutionError, DomainError)):
                raise
            with contextlib.suppress(OSError, ValueError, TypeError):
                logger.exception("Query %s failed", query_type.__name__)
            raise QueryExecutionError(
                query_type=query_type.__name__,
                error=str(e),
                cause=e,
            ) from e


__all__ = ["QueryBusImpl"]
