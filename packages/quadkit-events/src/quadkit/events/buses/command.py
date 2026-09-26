"""Command bus implementation.

The CommandBusProtocol dispatches commands to their handlers and supports:
- Single handler per command (enforced)
- Middleware pipeline (validation, logging, transactions)
- Explicit handler registration (no service locator)
"""

from __future__ import annotations

import contextlib
from typing import Any

from quadkit.contracts.exceptions.domain import DomainError
from quadkit.events.buses.base import Bus
from quadkit.events.exceptions import CommandExecutionError, HandlerNotFoundError
from quadkit.events.messages.command import Command
from quadkit.logging import get_logger

logger = get_logger(__name__)


from quadkit.contracts import CommandBusProtocol as CommandBusProtocol


class CommandBusImpl(Bus[Command, Any], CommandBusProtocol):
    """Command bus for dispatching commands.

    Handlers are registered explicitly via ``register()`` or through
    ``HandlerRegistry.register_with_buses()`` during provider registration.

    Example::

        # Commands are automatically routed to handlers
        result = await bus.dispatch(CreateOrderCommand(
            customer_id="cust-123",
            items=[...]
        ))
    """

    def __init__(
        self,
        middlewares: list[Any] | None = None,
        config: Any | None = None,
    ) -> None:
        """Initialize the command bus."""
        super().__init__(middlewares)
        self._config = config

    async def dispatch(self, command: Command) -> Any:
        """Dispatch a command for execution.

        Args:
            command: The command to execute.

        Returns:
            Command execution result.

        Raises:
            HandlerNotFoundError: If no handler is registered.
            CommandExecutionError: If command execution fails.
        """
        command_type = type(command)

        try:
            handler = await self._resolve_handler(command_type)
        except HandlerNotFoundError as e:
            raise HandlerNotFoundError("Command", command_type.__name__) from e

        try:
            return await self._execute_pipeline(command, handler)
        except Exception as e:  # noqa: BLE001 — the contract is: any execution failure becomes CommandExecutionError
            # DomainError is the caller's business-rule violation, not an
            # infrastructure failure: it must reach the web exception filter
            # intact, which maps NotFoundError/ConflictError/... to 404/409/...
            # Wrapping it would collapse every domain outcome into a 500.
            if isinstance(
                e, (HandlerNotFoundError, CommandExecutionError, DomainError)
            ):
                raise
            with contextlib.suppress(OSError, ValueError, TypeError):
                logger.exception("Command %s failed", command_type.__name__)
            raise CommandExecutionError(
                command_type=command_type.__name__,
                error=str(e),
                cause=e,
            ) from e


__all__ = ["CommandBusImpl"]
