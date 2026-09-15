"""GraphQL protocol definitions.

Protocols for GraphQL execution, schema building, data loading,
resolvers, and subscriptions.
"""

from __future__ import annotations

from quadkit.contracts.graphql.protocols.execution import (
    DEFAULT_SUBSCRIPTIONS_PATH as DEFAULT_SUBSCRIPTIONS_PATH,
)
from quadkit.contracts.graphql.protocols.execution import (
    DataLoaderProtocol as DataLoaderProtocol,
)
from quadkit.contracts.graphql.protocols.execution import (
    EntityResolverProtocol as EntityResolverProtocol,
)
from quadkit.contracts.graphql.protocols.execution import (
    GraphQLControllerProtocol as GraphQLControllerProtocol,
)
from quadkit.contracts.graphql.protocols.execution import (
    GraphQLExecutorProtocol as GraphQLExecutorProtocol,
)
from quadkit.contracts.graphql.protocols.execution import (
    ResolverProtocol as ResolverProtocol,
)
from quadkit.contracts.graphql.protocols.execution import (
    SchemaBuilderProtocol as SchemaBuilderProtocol,
)
from quadkit.contracts.graphql.protocols.playground import (
    GraphQLPlaygroundProtocol as GraphQLPlaygroundProtocol,
)
from quadkit.contracts.graphql.protocols.subscription import (
    DirectiveHandlerProtocol as DirectiveHandlerProtocol,
)
from quadkit.contracts.graphql.protocols.subscription import (
    MutationHandlerProtocol as MutationHandlerProtocol,
)
from quadkit.contracts.graphql.protocols.subscription import (
    SubscriptionAuthHandlerProtocol as SubscriptionAuthHandlerProtocol,
)
from quadkit.contracts.graphql.protocols.subscription import (
    SubscriptionHandlerProtocol as SubscriptionHandlerProtocol,
)
from quadkit.contracts.graphql.protocols.subscription import (
    WebSocketTransportProtocol as WebSocketTransportProtocol,
)
from quadkit.contracts.graphql.protocols.types import (
    ErrorFormatterProtocol as ErrorFormatterProtocol,
)
from quadkit.contracts.graphql.protocols.types import (
    GraphQLPrincipalResolverProtocol as GraphQLPrincipalResolverProtocol,
)
from quadkit.contracts.graphql.protocols.types import (
    GraphQLRequestProtocol as GraphQLRequestProtocol,
)
from quadkit.contracts.graphql.protocols.types import (
    IntrospectionHandlerProtocol as IntrospectionHandlerProtocol,
)
from quadkit.contracts.graphql.protocols.types import (
    ValidationRuleProtocol as ValidationRuleProtocol,
)

__all__ = [
    "DEFAULT_SUBSCRIPTIONS_PATH",
    "DataLoaderProtocol",
    "DirectiveHandlerProtocol",
    "EntityResolverProtocol",
    "ErrorFormatterProtocol",
    "GraphQLControllerProtocol",
    "GraphQLExecutorProtocol",
    "GraphQLPlaygroundProtocol",
    "GraphQLPrincipalResolverProtocol",
    "GraphQLRequestProtocol",
    "IntrospectionHandlerProtocol",
    "MutationHandlerProtocol",
    "ResolverProtocol",
    "SchemaBuilderProtocol",
    "SubscriptionAuthHandlerProtocol",
    "SubscriptionHandlerProtocol",
    "ValidationRuleProtocol",
    "WebSocketTransportProtocol",
]
