"""Secret store protocol for Quadkit Framework.

Provides a protocol for retrieving, storing, and deleting named secrets.
Implementations may delegate to environment variables, HashiCorp Vault,
AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, or a local
encrypted store, depending on the deployment environment.

Example::

    from quadkit.contracts.secrets import SecretStoreProtocol

    async def bootstrap(store: SecretStoreProtocol) -> None:
        api_key = await store.get_secret("stripe/api-key")
        db_url  = await store.get_secret("database/url")

Container registration::

    container.singleton(SecretStoreProtocol, EnvSecretStore)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretStoreProtocol(Protocol):
    """Protocol for retrieving, writing, and deleting named secrets.

    Secret names may use any naming convention; a hierarchical path
    (e.g. ``"database/password"``) is recommended for readability and
    to align with most provider APIs.

    All mutating operations (``set_secret``, ``delete_secret``) are
    **synchronous** at the protocol level — implementations may perform
    async I/O internally but the public contract accepts simple calls from
    both sync and async contexts.

    Example::

        store = EnvSecretStore()
        val = store.get_secret("MY_API_KEY")

    Async-first usage via a wrapping coroutine::

        val = await asyncio.to_thread(store.get_secret, "MY_API_KEY")
    """

    def get_secret(self, name: str) -> str:
        """Return the value of a secret by name.

        Args:
            name: Unique secret identifier (e.g. ``"stripe/api-key"``).

        Returns:
            The plaintext secret value.

        Raises:
            SecretNotFoundError: If no secret with that name exists.
            SecretAccessError: If the caller lacks permission.
        """
        ...

    def set_secret(self, name: str, value: str) -> None:
        """Write or overwrite a secret.

        Args:
            name: Unique secret identifier.
            value: Plaintext secret value to store.

        Raises:
            SecretAccessError: If the caller lacks permission to write.
        """
        ...

    def delete_secret(self, name: str) -> None:
        """Delete a secret by name.

        Non-existent secrets are silently ignored (idempotent delete).

        Args:
            name: Unique secret identifier.

        Raises:
            SecretAccessError: If the caller lacks permission to delete.
        """
        ...

    def has_secret(self, name: str) -> bool:
        """Return ``True`` if a secret with *name* exists, ``False`` otherwise.

        Args:
            name: Unique secret identifier.
        """
        ...


__all__ = [
    "SecretStoreProtocol",
]
