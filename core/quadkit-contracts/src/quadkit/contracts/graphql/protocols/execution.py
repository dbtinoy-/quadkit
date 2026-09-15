"""GraphQL execution and schema protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result
    from quadkit.contracts.exceptions.base import QuadkitError


# constant used by web layer when registering subscription routes
DEFAULT_SUBSCRIPTIONS_PATH: str = "/graphql/ws"


@runtime_checkable
class GraphQLExecutorProtocol(Protocol):
    """Protocol for GraphQL query execution."""

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        context: Any | None = None,
        operation_name: str | None = None,
    ) -> Result[dict[str, Any], QuadkitError]:
        """Execute a GraphQL query.

        Args:
            query: GraphQL query string
            variables: Query variables
            context: Execution context
            operation_name: Operation name for multi-operation queries

        Returns:
            Ok(result_dict) on success; Err(error) on transport-level failure
            (e.g. timeout, schema misconfiguration). GraphQL field-level errors
            are carried inside the Ok value via the ``errors`` key.
        """
        ...


@runtime_checkable
class GraphQLControllerProtocol(Protocol):
    """Marker protocol representing the HTTP controller for GraphQL.

    The web integration only needs to be able to resolve an instance from the
    container; no specific methods are required.
    """


@runtime_checkable
class SchemaBuilderProtocol(Protocol):
    """Protocol for building GraphQL schemas via a fluent interface."""

    def add_type(self, type_class: Any) -> SchemaBuilderProtocol:
        """Add an additional type to the schema.

        Args:
            type_class: The type class to add.

        Returns:
            Self for chaining.
        """
        ...

    def query(self, query_type: Any) -> SchemaBuilderProtocol:
        """Set the root query type.

        Args:
            query_type: The query type class.

        Returns:
            Self for chaining.
        """
        ...

    def mutation(self, mutation_type: Any) -> SchemaBuilderProtocol:
        """Set the root mutation type.

        Args:
            mutation_type: The mutation type class.

        Returns:
            Self for chaining.
        """
        ...

    def subscription(self, subscription_type: Any) -> SchemaBuilderProtocol:
        """Set the root subscription type.

        Args:
            subscription_type: The subscription type class.

        Returns:
            Self for chaining.
        """
        ...

    def add_extension(self, extension: Any) -> SchemaBuilderProtocol:
        """Register a schema extension.

        Args:
            extension: The extension instance (e.g. a Strawberry SchemaExtension).

        Returns:
            Self for chaining.
        """
        ...

    def add_dataloader(
        self,
        name: str,
        factory: Any,
    ) -> SchemaBuilderProtocol:
        """Register a DataLoaderProtocol factory for per-request loader initialisation.

        The factory is called once per request with the current
        :class:`GraphQLContext` as its sole argument and must return a
        DataLoaderProtocol instance.  All registered factories are forwarded to the
        :class:`ContextFactory` so loaders are available at resolve time via
        ``context.get_dataloader(name)``.

        Args:
            name: Unique loader name (used as the key in context).
            factory: Callable ``(context) -> DataLoaderProtocol`` that creates the
                loader for each request.

        Returns:
            Self for chaining.
        """
        ...

    def build(self) -> Any:
        """Build and return the configured GraphQL schema."""
        ...


@runtime_checkable
class DataLoaderProtocol(Protocol):
    """Protocol for GraphQL data loading (N+1 problem solution)."""

    async def load(self, key: Any) -> Any:
        """Load a single item by key."""
        ...

    async def load_many(self, keys: list[Any]) -> list[Any]:
        """Load multiple items by keys."""
        ...

    def prime(self, key: Any, value: Any) -> None:
        """Prime the cache with a key-value pair."""
        ...


@runtime_checkable
class ResolverProtocol(Protocol):
    """Protocol for GraphQL field resolvers."""

    async def resolve(
        self,
        parent: Any,
        args: dict[str, Any],
        context: Any,
        info: Any,
    ) -> Any:
        """Resolve a GraphQL field.

        Args:
            parent: Parent object
            args: Field arguments
            context: Execution context
            info: Field resolution info

        Returns:
            Resolved field value
        """
        ...


@runtime_checkable
class EntityResolverProtocol(Protocol):
    """Protocol for resolving entities in GraphQL federation."""

    async def resolve_reference(
        self,
        reference: dict[str, Any],
        context: Any,
        info: Any,
    ) -> Any | None:
        """Resolve an entity by reference.

        Args:
            reference: Entity reference
            context: Execution context
            info: Resolution info

        Returns:
            Resolved entity or None
        """
        ...
