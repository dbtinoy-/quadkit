"""Shared provider helper functions."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.contracts.security.stores import AsyncSecretStoreProtocol


async def resolve_optional(container: Any, protocol: type) -> Any:
    """Resolve a protocol optionally, returning None if unavailable.

    Args:
        container: The container to resolve from.
        protocol: The protocol type to resolve.

    Returns:
        The resolved service, or None when unavailable.
    """
    resolver = getattr(container, "resolve_optional", None)
    if resolver is not None:
        return await resolver(protocol)
    try:
        return await container.resolve(protocol)
    except (LookupError, KeyError, ValueError, TypeError):
        return None


async def resolve_credential(
    secret_store: AsyncSecretStoreProtocol | None, secret_name: str
) -> str | None:
    """Resolve a secret by name via the secret store, else env var.

    Args:
        secret_store: Optional secret store to consult first.
        secret_name: Name of the secret to resolve.

    Returns:
        The resolved secret value, or None when absent.
    """
    if secret_store is not None:
        value = await secret_store.get(secret_name)
        if value:
            return value
    return os.environ.get(secret_name.upper())


__all__ = ["resolve_credential", "resolve_optional"]
