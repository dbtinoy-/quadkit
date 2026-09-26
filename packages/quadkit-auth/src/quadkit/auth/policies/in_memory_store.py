"""In-memory policy store for development and testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.auth.policies.types import Policy


class InMemoryPolicyStore:
    """In-memory policy storage for development and testing.

    This store is NOT suitable for production as it does not persist data
    across restarts.
    """

    def __init__(self) -> None:
        self._policies: dict[str, Policy] = {}

    async def get_all(self) -> list[Policy]:
        """Get all policies."""
        return list(self._policies.values())

    async def get_by_id(self, policy_id: str) -> Policy | None:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    async def get_by_name(self, name: str) -> Policy | None:
        """Get a policy by name."""
        for policy in self._policies.values():
            if policy.name == name:
                return policy
        return None

    async def save(self, policy: Policy) -> None:
        """Save a policy."""
        self._policies[policy.policy_id] = policy

    async def delete(self, policy_id: str) -> bool:
        """Delete a policy."""
        if policy_id in self._policies:
            del self._policies[policy_id]
            return True
        return False

    async def exists(self, policy_id: str) -> bool:
        """Check if a policy exists."""
        return policy_id in self._policies

    def clear(self) -> None:
        """Clear all policies."""
        self._policies.clear()


__all__ = [
    "InMemoryPolicyStore",
]
