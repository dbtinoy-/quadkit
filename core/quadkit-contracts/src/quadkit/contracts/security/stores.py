"""Async persistent secret store protocol.

Unlike the synchronous :class:`~quadkit.contracts.security.secrets.SecretStoreProtocol`
(which targets external secret managers such as Vault or AWS Secrets Manager),
this protocol targets database-backed secret tables where async I/O is required.
It is intentionally minimal — no rotation, no versioning — leaving those concerns
to the implementation layer.

Implementations ship in ``quadkit-sql`` (``quadkit.sql.stores``) so they can share
the application's database connection pool.

Example::

    from quadkit.contracts.security.stores import AsyncSecretStoreProtocol

    store = await container.resolve(AsyncSecretStoreProtocol)
    token = await store.get("stripe_api_key")
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AsyncSecretStoreProtocol(Protocol):
    """Async persistent store for sensitive named secret values.

    Typical usage::

        store = await container.resolve(AsyncSecretStoreProtocol)
        token = await store.get("stripe_api_key")
    """

    async def get(self, name: str) -> str | None:
        """Return the secret value for *name*, or ``None`` if absent.

        Args:
            name: Unique secret identifier.
        """
        ...

    async def get_bulk(self, *names: str) -> dict[str, str]:
        """Return a mapping of name → value for all requested secrets.

        Args:
            names: One or more secret names.

        Returns:
            Dict containing only the names that were found.
        """
        ...

    async def set(self, name: str, value: str) -> None:
        """Write or overwrite a secret value.

        Args:
            name: Unique secret identifier.
            value: Plaintext secret value.
        """
        ...

    async def delete(self, name: str) -> None:
        """Remove a secret.  No-op if absent.

        Args:
            name: Unique secret identifier.
        """
        ...


__all__ = ["AsyncSecretStoreProtocol"]
