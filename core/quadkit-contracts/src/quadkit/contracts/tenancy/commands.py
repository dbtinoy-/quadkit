"""Tenancy command value objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CreateTenantCommand:
    """Command to create a new tenant.

    Attributes:
        slug: URL-safe, human-readable identifier for the new tenant.
        name: Display name of the tenant.
        plan: Optional subscription plan name.
        config: Static provisioning configuration.
        metadata: Arbitrary application-defined metadata.
    """

    slug: str
    name: str
    plan: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateTenantCommand:
    """Command to update an existing tenant's mutable fields.

    All fields are optional. Only non-``None`` fields are applied.

    Attributes:
        name: New display name (optional).
        plan: New subscription plan (optional).
        config: Replacement static config snapshot (optional).
        metadata: Replacement metadata (optional).
    """

    name: str | None = None
    plan: str | None = None
    config: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


__all__ = [
    "CreateTenantCommand",
    "UpdateTenantCommand",
]
