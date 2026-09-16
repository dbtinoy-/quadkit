"""Tenant-aware graph isolation strategy and collection resolver types."""

from __future__ import annotations

from enum import Enum


class GraphTenancyStrategy(str, Enum):
    """Strategy for isolating tenant data in a graph store.

    ``NODE_PROPERTY``
        Every node and edge carries a ``tenant_id`` property; queries
        auto-inject a property filter to scope results to the current
        tenant.  Works with any backend and is the default strategy.

    ``GRAPH_PER_TENANT``
        Each tenant gets a separate named graph (or Neo4j database).
        Graph names are resolved from the current tenant context via
        a ``TenantCollectionResolver``.
    """

    NODE_PROPERTY = "node_property"
    GRAPH_PER_TENANT = "graph_per_tenant"


__all__ = ["GraphTenancyStrategy"]
