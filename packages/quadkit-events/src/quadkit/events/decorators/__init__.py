"""Quadkit CQRS Decorators.

This module provides decorator-based handler registration for a more
concise and Pythonic way to define command, query, and event handlers.

Example:
    ```python
    from quadkit.events.decorators import command_handler, query_handler, event_handler

    @command_handler(CreateUserCommand)
    async def handle_create_user(command: CreateUserCommand) -> str:
        user = await create_user(command.name, command.email)
        return user.user_id

    @query_handler(GetUserQuery)
    async def handle_get_user(query: GetUserQuery) -> UserDTO:
        return await fetch_user(query.user_id)

    @event_handler(UserCreatedEvent)
    async def on_user_created(event: UserCreatedEvent) -> None:
        await send_welcome_email(event.email)
    ```
"""

from __future__ import annotations

from quadkit.events.decorators.encryption import encrypted_event
from quadkit.events.decorators.handlers import (
    HandlerInfo,
    clear_handlers,
    command_handler,
    event_handler,
    get_all_handlers,
    get_handler_info,
    multi_event_handler,
    projection,
    query_handler,
    saga,
    set_handler_info,
)
from quadkit.events.decorators.validation import (
    clear_idempotency_cache,
    idempotent,
    validate,
    validate_command,
    validate_query,
)
from quadkit.events.handlers.registry import clear_handler_registry

__all__ = [
    "HandlerInfo",
    "clear_handler_registry",
    "clear_handlers",
    "clear_idempotency_cache",
    "command_handler",
    "encrypted_event",
    "event_handler",
    "get_all_handlers",
    "get_handler_info",
    "idempotent",
    "multi_event_handler",
    "projection",
    "query_handler",
    "saga",
    "set_handler_info",
    "validate",
    "validate_command",
    "validate_query",
]
