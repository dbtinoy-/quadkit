"""GraphQL validation, formatting, and request protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.graphql.types import GraphQLPrincipal


@runtime_checkable
class ValidationRuleProtocol(Protocol):
    """Protocol for GraphQL query validators (depth, complexity, alias, etc.).

    Implementations perform a single focused check on a parsed document
    and raise a :class:`~quadkit.graphql.exceptions.GraphQLError`
    subclass on failure.  A no-op return indicates the document passed.

    All three built-in validators — :class:`DepthLimitValidator`,
    :class:`ComplexityAnalyzer`, and :class:`AliasLimitValidator` —
    satisfy this protocol.
    """

    def validate(self, document: Any) -> None:
        """Validate a GraphQL document; raise on failure.

        Args:
            document: Parsed GraphQL document (a ``graphql-core``
                ``DocumentNode`` in practice, typed as ``Any`` to avoid
                a hard compile-time dependency on ``graphql-core``).

        Raises:
            GraphQLBaseError: If the document violates this rule.
        """
        ...


@runtime_checkable
class ErrorFormatterProtocol(Protocol):
    """Protocol for formatting GraphQL errors.

    Implementations receive the error only; any request-scoped data
    (e.g. request_id, user) must be accessed via the shared execution context
    rather than as a method parameter.
    """

    def format_error(
        self,
        error: Any,
    ) -> dict[str, Any]:
        """Format a GraphQL error for response.

        Args:
            error: GraphQL error object.

        Returns:
            Formatted error dictionary conforming to the GraphQL error spec.
        """
        ...


@runtime_checkable
class GraphQLRequestProtocol(Protocol):
    """Protocol for HTTP requests processed by the GraphQL controller.

    Decouples ``GraphQLController`` from concrete web-framework types
    (e.g. Starlette ``Request``) so that the graphql package does not
    create a cross-extension import dependency on ``quadkit-web``.

    Any framework request object that exposes these members satisfies
    the protocol at runtime.
    """

    state: Any
    """Mutable per-request state bag (e.g. ``request.state``)."""

    scope: dict[str, Any]
    """ASGI connection scope dictionary."""

    async def json(self) -> Any:
        """Deserialise the request body as JSON.

        Returns:
            Parsed JSON value (typically a ``dict``).
        """
        ...


@runtime_checkable
class IntrospectionHandlerProtocol(Protocol):
    """Protocol for GraphQL introspection.

    Implementations perform full schema introspection and return the
    standard GraphQL introspection result.
    """

    async def introspect(self, context: Any) -> dict[str, Any]:
        """Perform GraphQL introspection.

        Args:
            context: Introspection context

        Returns:
            Introspection result
        """
        ...


@runtime_checkable
class GraphQLPrincipalResolverProtocol(Protocol):
    """Protocol for resolving GraphQL principals from authentication sources.

    Implementations transform raw authentication data (e.g., decoded JWT,
    OAuth2 user object) into a framework-standard :class:`GraphQLPrincipal`
    for use in the GraphQL execution context.

    This decouples the GraphQL layer from authentication implementation
    details and enables consistent principal access across all resolvers.
    """

    async def resolve_principal(
        self,
        user: Any,
        request: Any = None,
    ) -> GraphQLPrincipal:
        """Resolve a GraphQLPrincipal from the authenticated user.

        Args:
            user: Raw authenticated user object from the authentication
                layer (e.g., decoded JWT payload, OAuth2 user dict).
            request: Optional HTTP request object for additional context
                (e.g., extracting headers, client IP).

        Returns:
            A :class:`GraphQLPrincipal` with identity fields populated
            from the authentication source.
        """
        ...
