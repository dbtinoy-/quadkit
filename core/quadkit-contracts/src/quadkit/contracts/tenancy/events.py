"""Tenancy domain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class TenantProvisioned:
    """Published when a new tenant is fully provisioned and active.

    Attributes:
        tenant_id: Unique identifier of the newly provisioned tenant.
        slug: URL-safe slug for the tenant.
        plan: Subscription plan assigned at creation (if any).
        timestamp: UTC timestamp of the provisioning event.
    """

    tenant_id: str
    slug: str
    plan: str | None
    timestamp: datetime


@dataclass(frozen=True)
class TenantActivated:
    """Published when a previously inactive or suspended tenant is activated.

    Attributes:
        tenant_id: Unique identifier of the activated tenant.
        timestamp: UTC timestamp of the activation event.
    """

    tenant_id: str
    timestamp: datetime


@dataclass(frozen=True)
class TenantSuspended:
    """Published when a tenant is suspended.

    Attributes:
        tenant_id: Unique identifier of the suspended tenant.
        reason: Human-readable reason for the suspension (optional).
        timestamp: UTC timestamp of the suspension event.
    """

    tenant_id: str
    reason: str | None
    timestamp: datetime


@dataclass(frozen=True)
class TenantDeactivated:
    """Published when a tenant is deactivated.

    Attributes:
        tenant_id: Unique identifier of the deactivated tenant.
        timestamp: UTC timestamp of the deactivation event.
    """

    tenant_id: str
    timestamp: datetime


@dataclass(frozen=True)
class TenantConfigChanged:
    """Published when a per-tenant configuration value is updated.

    Attributes:
        tenant_id: Unique identifier of the tenant whose config changed.
        key: Configuration key that was modified.
        old_value: The previous value (may be ``None`` if newly set).
        new_value: The new value.
        timestamp: UTC timestamp of the configuration change event.
    """

    tenant_id: str
    key: str
    old_value: Any
    new_value: Any
    timestamp: datetime


@dataclass(frozen=True)
class TenantTierMigrationStarted:
    """Published when a tenant tier migration begins.

    Attributes:
        tenant_id: The tenant being migrated.
        source_tier: The isolation tier being migrated from.
        target_tier: The isolation tier being migrated to.
        saga_id: The saga instance identifier for tracking.
        timestamp: UTC timestamp of the event.
    """

    tenant_id: str
    source_tier: str
    target_tier: str
    saga_id: str
    timestamp: datetime


@dataclass(frozen=True)
class TenantTierMigrationSucceeded:
    """Published when a tenant tier migration completes successfully.

    Attributes:
        tenant_id: The tenant that was migrated.
        source_tier: The isolation tier migrated from.
        target_tier: The isolation tier migrated to.
        saga_id: The saga instance identifier for tracking.
        duration_ms: Wall-clock duration of the migration in milliseconds.
        timestamp: UTC timestamp of the event.
    """

    tenant_id: str
    source_tier: str
    target_tier: str
    saga_id: str
    duration_ms: int
    timestamp: datetime


@dataclass(frozen=True)
class TenantTierMigrationFailed:
    """Published when a tenant tier migration fails.

    Attributes:
        tenant_id: The tenant that failed migration.
        source_tier: The isolation tier being migrated from.
        target_tier: The isolation tier being migrated to.
        saga_id: The saga instance identifier for tracking.
        error: Human-readable description of the failure.
        timestamp: UTC timestamp of the event.
    """

    tenant_id: str
    source_tier: str
    target_tier: str
    saga_id: str
    error: str
    timestamp: datetime


@dataclass(frozen=True)
class TenantTierMigrationCheckpoint:
    """Published when a saga stage checkpoint is reached during migration.

    Attributes:
        tenant_id: The tenant being migrated.
        saga_id: The saga instance identifier.
        stage: The stage name (e.g. ``"validate"``, ``"copy_data"``).
        status: The stage status (e.g. ``"completed"``, ``"failed"``).
        timestamp: UTC timestamp of the checkpoint.
    """

    tenant_id: str
    saga_id: str
    stage: str
    status: str
    timestamp: datetime


__all__ = [
    "TenantActivated",
    "TenantConfigChanged",
    "TenantDeactivated",
    "TenantProvisioned",
    "TenantSuspended",
    "TenantTierMigrationCheckpoint",
    "TenantTierMigrationFailed",
    "TenantTierMigrationStarted",
    "TenantTierMigrationSucceeded",
]
