"""Tenant tier migration contracts — copy strategy, value types, and constants."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

TIER_ISOLATION_MAP: dict[str, str] = {
    "m1": "row_level",
    "m2": "row_level",
    "m3": "schema",
    "m4": "schema",
    "m5": "schema",
    "m6": "database",
    "m7": "database",
    "m8": "database",
}

ISOLATION_TIER_ORDER: list[str] = ["row_level", "schema", "database"]


@dataclass(frozen=True)
class SnapshotResult:
    """Record counts before and after a copy operation."""

    before_count: int
    after_count: int


@dataclass(frozen=True)
class CopyResult:
    """Result of a copy operation carried by the migration copy strategy."""

    records_copied: int
    records_failed: int
    errors: list[str] = field(default_factory=list)
    source_snapshot: SnapshotResult | None = None
    target_snapshot: SnapshotResult | None = None


@dataclass(frozen=True)
class MigrationContext:
    """Carries source and target isolation context for a copy strategy."""

    source_tier: str
    target_tier: str
    source_strategy_name: str
    target_strategy_name: str
    source_config: dict[str, Any] = field(default_factory=dict)
    target_config: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class MigrationCopyStrategy(Protocol):
    """Copies tenant data from source isolation to target isolation.

    Implementations raise ``RuntimeError`` or ``ValueError`` on failure so
    that the parent saga triggers compensation.
    """

    async def validate(self, tenant_id: str, context: MigrationContext) -> None:
        """Verify source and target are compatible.

        Raises:
            ValueError: If the migration path is invalid.
        """

    async def copy(self, tenant_id: str, context: MigrationContext) -> CopyResult:
        """Execute the data copy.

        Returns:
            A ``CopyResult`` summarising the operation.

        Raises:
            RuntimeError: If the copy fails.
        """

    async def rollback(self, tenant_id: str, result: CopyResult) -> None:
        """Undo a completed copy operation.

        Raises:
            RuntimeError: If the rollback fails.
        """


__all__ = [
    "ISOLATION_TIER_ORDER",
    "TIER_ISOLATION_MAP",
    "CopyResult",
    "MigrationContext",
    "MigrationCopyStrategy",
    "SnapshotResult",
]
