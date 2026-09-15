"""Tenant-aware collection resolution protocols for vector stores."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TenantCollectionResolver(Protocol):
    """Resolve a logical collection name to a tenant-specific name.

    Implementations transform a logical name (e.g. ``"canon"``) into a
    tenant-scoped physical name (e.g. ``"canon_t_t1"``) using the
    current tenant context.
    """

    def resolve(self, logical_name: str, tenant_id: str) -> str:
        """Resolve a logical collection name for the given tenant.

        Args:
            logical_name: The logical collection name used by application code.
            tenant_id: The current tenant identifier.

        Returns:
            A tenant-scoped collection name.
        """
        ...


__all__ = ["TenantCollectionResolver"]
