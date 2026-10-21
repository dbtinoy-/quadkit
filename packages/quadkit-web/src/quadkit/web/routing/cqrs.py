"""CQRSController - Controller base class with integrated CQRS command/query bus dispatch.

Provides a controller that can dispatch commands and queries through the CQRS buses
registered in the DI container. Controllers extending this class get typed
``dispatch_command`` and ``dispatch_query`` helper methods.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.events import CommandBusProtocol, QueryBusProtocol
from quadkit.logging import get_logger
from quadkit.web.routing.controllers import Controller

logger = get_logger(__name__)


class CQRSController(Controller):
    """Controller with built-in CQRS command and query bus dispatch.

    Subclass this instead of ``Controller`` when your endpoints need to
    dispatch commands or queries through the CQRS buses.

    The buses are injected via the constructor and are expected to be
    resolved from the DI container.

    Example::

        from quadkit.serialization.domain import json_serialize
        from quadkit.web import JSONResponse

        class OrderController(CQRSController):
            @post("/orders")
            async def create_order(self, request: Request) -> JSONResponse:
                data = await request.json()
                result = await self.dispatch_command(CreateOrderCommand(**data))
                return JSONResponse({"id": result.id}, status_code=201)

            @get("/orders/{order_id}")
            async def get_order(self, request: Request) -> JSONResponse:
                order_id = request.path_params["order_id"]
                result = await self.dispatch_query(GetOrderQuery(order_id=order_id))
                return JSONResponse(json_serialize(result))
    """

    def __init__(
        self,
        command_bus: CommandBusProtocol | None = None,
        query_bus: QueryBusProtocol | None = None,
    ) -> None:
        """Initialize CQRSController with optional command and query buses.

        Args:
            command_bus: CommandBusProtocol implementation for dispatching commands.
                If None, calling ``dispatch_command`` will raise RuntimeError.
            query_bus: QueryBusProtocol implementation for executing queries.
                If None, calling ``dispatch_query`` will raise RuntimeError.
        """
        super().__init__()
        self._command_bus = command_bus
        self._query_bus = query_bus

    async def dispatch_command(self, command: Any) -> Any:
        """Dispatch a command through the command bus.

        Args:
            command: The command object to dispatch.

        Returns:
            The result returned by the command handler.

        Raises:
            RuntimeError: If no CommandBusProtocol was provided to this controller.
        """
        if self._command_bus is None:
            raise RuntimeError(
                f"{type(self).__name__} has no CommandBusProtocol configured. "
                "Register a CommandBusProtocol in the DI container.",
            )
        return await self._command_bus.dispatch(command)

    async def dispatch_query(self, query: Any) -> Any:
        """Dispatch a query through the query bus.

        Args:
            query: The query object to execute.

        Returns:
            The query result.

        Raises:
            RuntimeError: If no QueryBusProtocol was provided to this controller.
        """
        if self._query_bus is None:
            raise RuntimeError(
                f"{type(self).__name__} has no QueryBusProtocol configured. "
                "Register a QueryBusProtocol in the DI container.",
            )
        return await self._query_bus.execute(query)
