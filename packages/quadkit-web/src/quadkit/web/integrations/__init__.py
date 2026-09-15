"""Framework integrations: authentication, debugging, GraphQL, rate limiting."""

from __future__ import annotations

from quadkit.web.integrations.auth import AuthIntegration
from quadkit.web.integrations.cache import CacheIntegration
from quadkit.web.integrations.debug import DebugIntegration
from quadkit.web.integrations.graphql import GraphQLIntegration
from quadkit.web.integrations.rate_limit import RateLimitIntegration
from quadkit.web.integrations.setup import lifespan
from quadkit.web.integrations.sql import SQLIntegration
from quadkit.web.integrations.throttle import RateLimitModule, throttle

__all__ = [
    "AuthIntegration",
    "CacheIntegration",
    "DebugIntegration",
    "GraphQLIntegration",
    "RateLimitIntegration",
    "RateLimitModule",
    "SQLIntegration",
    "lifespan",
    "throttle",
]
