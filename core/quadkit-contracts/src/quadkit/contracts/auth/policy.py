"""Policy-store protocol for the ABAC policy engine.

Defines :class:`PolicyStoreProtocol`, the contract for loading, persisting, and
querying ABAC policies.  Multiple back-ends (in-memory, YAML file,
database, remote service) can satisfy this protocol through structural
subtyping, making the :class:`PolicyEngine` independently testable.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

__all__ = ["PolicyStoreProtocol"]


@runtime_checkable
class PolicyStoreProtocol(Protocol):
    """Storage protocol for ABAC authorization policies.

    Implementations are responsible for persisting and retrieving
    :class:`~the optional provider module` objects.  The
    concrete ``Policy`` type is referenced as ``Any`` here so that the
    contracts package remains dependency-free.

    Example::

        class YAMLPolicyStore:
            def __init__(self, path: Path) -> None:
                self._path = path

            async def load_policies(self) -> list[Any]:
                with open(self._path) as f:
                    raw = yaml.safe_load(f)
                return [Policy(**p) for p in raw["policies"]]

            async def save_policy(self, policy: Any) -> None:
                ...   # Append/update in YAML file
    """

    async def load_policies(self) -> list[Any]:
        """Load all policies from the store.

        Returns:
            List of policy objects ordered by their natural storage order.
        """
        ...

    async def save_policy(self, policy: Any) -> None:
        """Persist a single policy.

        Args:
            policy: The policy object to save.  Implementations should
                generate the ``id`` field if it is absent.
        """
        ...

    async def delete_policy(self, policy_id: str) -> bool:
        """Remove a policy by its identifier.

        Args:
            policy_id: Unique policy identifier.

        Returns:
            True if the policy was found and removed, False otherwise.
        """
        ...

    async def get_policy(self, policy_id: str) -> Any | None:
        """Retrieve a single policy by ID.

        Args:
            policy_id: Unique policy identifier.

        Returns:
            The policy if found, None otherwise.
        """
        ...
