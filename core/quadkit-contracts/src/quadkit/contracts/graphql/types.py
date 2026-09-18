"""GraphQL type definitions.

Shared types for GraphQL execution context and principal resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GraphQLPrincipal:
    """Unified principal representation for GraphQL context.

    Provides a common interface for accessing user identity across
    the framework, decoupling GraphQL resolvers from authentication
    implementation details.

    All fields default to ``None`` to support unauthenticated requests
    and partial principal information from different authentication
    sources (JWT, OAuth2, API keys, etc.).

    Attributes:
        internal_user_id: Framework-internal user identifier (e.g., database PK).
        subject_id: External subject identifier (e.g., JWT ``sub`` claim, OAuth2 user ID).
        email: User email address, if available.
        raw_user: Original authentication payload (e.g., decoded JWT, OAuth2 user object).
    """

    internal_user_id: str | None = None
    subject_id: str | None = None
    email: str | None = None
    raw_user: Any | None = None


__all__ = [
    "GraphQLPrincipal",
]
