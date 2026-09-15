"""Tenancy value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TenantStatus(str, Enum):
    """Lifecycle status of a tenant.

    Attributes:
        ACTIVE: Tenant is fully operational and accepts requests.
        INACTIVE: Tenant has been deactivated and no longer accepts requests.
        SUSPENDED: Tenant has been suspended (e.g. for non-payment) and is
            temporarily blocked from accessing the system.
        PROVISIONING: Tenant is being created; isolation resources are being
            set up.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PROVISIONING = "provisioning"


@dataclass(frozen=True)
class TenantInfo:
    """Core tenant identity record.

    The ``config`` field here is the tenant's *static* provisioning config
    (plan limits, feature flags set at creation time). Runtime per-tenant
    overrides are managed separately by ``TenantConfigProviderProtocol`` /
    ``TenantConfigService``. The two are independent — ``TenantInfo.config``
    is a snapshot stored alongside the tenant record; ``TenantConfigService``
    is a live, cached, key-value overlay.

    Attributes:
        tenant_id: Unique identifier for the tenant.
        slug: URL-safe, human-readable identifier (e.g. ``acme-corp``).
        name: Display name of the tenant.
        status: Current lifecycle status.
        plan: Subscription plan name (optional).
        config: Static provisioning configuration snapshot.
        metadata: Arbitrary application-defined metadata.
        created_at: Timestamp when the tenant was created.
    """

    tenant_id: str
    slug: str
    name: str
    status: TenantStatus
    plan: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None


@dataclass(frozen=True)
class TenantResolutionContext:
    """Immutable snapshot of request data available for tenant resolution.

    Passed to every :class:`~quadkit.contracts.tenancy.protocols.TenantResolverProtocol`
    during the resolution chain so resolvers can inspect request metadata
    without depending on any web framework type.

    Attributes:
        headers: HTTP request headers (lowercased keys).
        host: The ``Host`` header value (e.g. ``acme.app.com``).
        path: The request path (e.g. ``/api/tenants/acme/users``).
        claims: Decoded JWT claims from the current authentication context.
    """

    headers: dict[str, str]
    host: str | None = None
    path: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)


__all__ = [
    "TenantInfo",
    "TenantResolutionContext",
    "TenantStatus",
]
