"""Quadkit CQRS Schema Management.

This module provides schema management for events, including:
- Schema Registry: Central registry for event schemas
- Schema Evolution: Version upgrades and migrations
- Schema Migration: Tools for migrating event data

Example:
    ```python
    from quadkit.events.schema import (
        SchemaRegistry,
        EventSchema,
        Upcaster,
        SchemaEvolution
    )

    # Register schemas
    registry = SchemaRegistry()
    await registry.register_schema(user_created_v1_schema)
    await registry.register_schema(user_created_v2_schema)

    # Define upcaster
    class UserCreatedV1ToV2(Upcaster):
        source_version = 1
        target_version = 2

        async def upcast(self, data: dict) -> dict:
            data["display_name"] = data.get("username", "")
            return data

    # Migrate events
    evolution = SchemaEvolution(registry)
    migrated = await evolution.migrate_event(event, target_version=2)
    ```
"""

from __future__ import annotations

from quadkit.events.schema.evolution import (
    Downcaster,
    EventMigrator,
    SchemaEvolution,
    Upcaster,
)
from quadkit.events.schema.migration import (
    MigrationConfig,
    MigrationProgress,
    MigrationResult,
    MigrationScheduler,
    MigrationStatus,
    SchemaMigrator,
)
from quadkit.events.schema.registry import (
    EventSchema,
    InMemorySchemaStore,
    SchemaRegistry,
    SchemaStore,
)

__all__ = [
    "Downcaster",
    "EventMigrator",
    "EventSchema",
    "InMemorySchemaStore",
    "MigrationConfig",
    "MigrationProgress",
    "MigrationResult",
    "MigrationScheduler",
    "MigrationStatus",
    "SchemaEvolution",
    "SchemaMigrator",
    "SchemaRegistry",
    "SchemaStore",
    "Upcaster",
]
