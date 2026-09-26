from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.auth.models import UserIdentityProtocol
    from quadkit.contracts.core.types import TokenPayload


@runtime_checkable
class TokenValidatorProtocol(Protocol):
    """Validates and decodes authentication tokens."""

    async def validate(self, token: str) -> TokenPayload | None:
        """Validate a token and return its payload, or None if invalid."""
        ...

    async def revoke(self, token: str) -> bool:
        """Revoke a token, preventing future validation."""
        ...


@runtime_checkable
class IdentityResolverProtocol(Protocol):
    """Resolves a token payload to a concrete user identity."""

    async def resolve(self, payload: TokenPayload) -> UserIdentityProtocol | None:
        """Resolve token payload to user identity."""
        ...
