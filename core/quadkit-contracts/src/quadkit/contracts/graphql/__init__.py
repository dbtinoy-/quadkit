"""GraphQL protocols."""

from __future__ import annotations

from quadkit.contracts.graphql.protocols import (
    DataLoaderProtocol,
    DirectiveHandlerProtocol,
    EntityResolverProtocol,
    ErrorFormatterProtocol,
    GraphQLExecutorProtocol,
    GraphQLPlaygroundProtocol,
    GraphQLPrincipalResolverProtocol,
    GraphQLRequestProtocol,
    IntrospectionHandlerProtocol,
    MutationHandlerProtocol,
    ResolverProtocol,
    SchemaBuilderProtocol,
    SubscriptionAuthHandlerProtocol,
    SubscriptionHandlerProtocol,
    ValidationRuleProtocol,
    WebSocketTransportProtocol,
)
from quadkit.contracts.graphql.types import GraphQLPrincipal

__all__ = [
    "DataLoaderProtocol",
    "DirectiveHandlerProtocol",
    "EntityResolverProtocol",
    "ErrorFormatterProtocol",
    "GraphQLExecutorProtocol",
    "GraphQLPlaygroundProtocol",
    "GraphQLPrincipal",
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
