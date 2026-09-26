"""Policy store protocols for ABAC policy persistence."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.auth.policies.types import Policy


@runtime_checkable
class PolicyStoreProtocol(Protocol):
    """Protocol for policy storage backends.

    Implement this protocol to provide custom policy storage
    (database, file, remote service, etc.).
    """

    async def get_all(self) -> list[Policy]:
        """Get all policies from the store.

        Returns:
            List of all policies.
        """
        ...

    async def get_by_id(self, policy_id: str) -> Policy | None:
        """Get a policy by its ID.

        Args:
            policy_id: The policy ID.

        Returns:
            The policy if found, None otherwise.
        """
        ...

    async def get_by_name(self, name: str) -> Policy | None:
        """Get a policy by its name.

        Args:
            name: The policy name.

        Returns:
            The policy if found, None otherwise.
        """
        ...

    async def save(self, policy: Policy) -> None:
        """Save a policy to the store.

        Args:
            policy: The policy to save.
        """
        ...

    async def delete(self, policy_id: str) -> bool:
        """Delete a policy from the store.

        Args:
            policy_id: The policy ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def exists(self, policy_id: str) -> bool:
        """Check if a policy exists.

        Args:
            policy_id: The policy ID.

        Returns:
            True if exists, False otherwise.
        """
        ...


@runtime_checkable
class PolicyLoader(Protocol):
    """Protocol for loading policies from various sources.

    Used to load policies from files, databases, or remote services.
    """

    async def load(self) -> list[Policy]:
        """Load policies from the source.

        Returns:
            List of loaded policies.
        """
        ...

    async def reload(self) -> list[Policy]:
        """Reload policies from the source.

        Returns:
            List of reloaded policies.
        """
        ...


__all__ = [
    "PolicyLoader",
    "PolicyStoreProtocol",
]
