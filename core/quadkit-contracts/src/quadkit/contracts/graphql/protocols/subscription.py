"""GraphQL subscription, mutation, and transport protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@runtime_checkable
class SubscriptionHandlerProtocol(Protocol):
    """Protocol for field-level GraphQL subscription resolvers.

    Implementations produce an async iterable of events for a single
    subscription field.  This is the *resolver-level* contract; for the
    WebSocket transport protocol see :class:`WebSocketTransportProtocol`.
    """

    async def subscribe(
        self,
        field_name: str,
        args: dict[str, Any],
        context: Any,
        info: Any,
    ) -> AsyncIterator[Any]:
        """Yield events for the named subscription field.

        Args:
            field_name: Subscription field name
            args: Subscription arguments
            context: Execution context
            info: Field resolution info

        Yields:
            Subscription events
        """
        ...


@runtime_checkable
class SubscriptionAuthHandlerProtocol(Protocol):
    """Protocol for per-subscription authorization checks.

    Invoked during ``_handle_subscribe`` before the subscription is
    established.  Return ``False`` to reject the subscription.

    This is a *per-subscription* check distinct from the connection-level
    authentication performed by ``SubscriptionAuth.authenticate`` during
    ``connection_init``.
    """

    async def authorize(
        self,
        user: Any,
        operation_name: str | None,
        query: str | None,
    ) -> bool:
        """Authorize a subscription request.

        Args:
            user: The authenticated user from the connection context,
                or ``None`` when no authentication handler is configured.
            operation_name: The GraphQL operation name, if provided.
            query: The raw GraphQL query string.

        Returns:
            ``True`` if the subscription is authorized, ``False`` to reject.
        """
        ...


@runtime_checkable
class WebSocketTransportProtocol(Protocol):
    """Protocol for WebSocket-level GraphQL subscription transport.

    Describes the connection-handler contract for classes that manage
    the full lifecycle of a WebSocket subscription session (e.g.
    the ``graphql-transport-ws`` protocol).  It is satisfied structurally
    by :class:`~quadkit.graphql.subscriptions.transport.GraphQLWSTransport`.

    This is deliberately separate from :class:`SubscriptionHandler` which
    operates at the field-resolver level.
    """

    async def handle(self, websocket: Any, app: Any | None = None) -> None:
        """Handle a single WebSocket connection for the entire session.

        Implementations should accept the WebSocket, drive the
        protocol handshake, stream subscription events, and clean up
        on disconnect.

        Args:
            websocket: A ``WebSocketProtocol``-compatible connection
                (typed as ``Any`` to avoid a hard Starlette dependency
                in the contracts layer).
            app: Optional application instance for DI / container
                resolution.
        """
        ...


@runtime_checkable
class MutationHandlerProtocol(Protocol):
    """Protocol for GraphQL mutation handling."""

    async def mutate(
        self,
        field_name: str,
        args: dict[str, Any],
        context: Any,
        info: Any,
    ) -> Any:
        """Handle a GraphQL mutation.

        Args:
            field_name: Mutation field name
            args: Mutation arguments
            context: Execution context
            info: Field info

        Returns:
            Mutation result
        """
        ...


@runtime_checkable
class DirectiveHandlerProtocol(Protocol):
    """Protocol for GraphQL directive handling."""

    def apply_directive(
        self,
        directive_name: str,
        args: dict[str, Any],
        target: Any,
    ) -> Any:
        """Apply a GraphQL directive.

        Args:
            directive_name: Directive name
            args: Directive arguments
            target: Target object to apply directive to

        Returns:
            Modified target object
        """
        ...
