"""Scenario tests for schema evolution and the event migrator.

Drives the real ``SchemaEvolution`` / ``SchemaRegistry`` / ``SchemaMigrator``
stack: upcaster registration and multi-step migration paths, data-level
migration with version stamping (regression coverage for the registry
event-class registration crash and the missing ``schema_version`` stamp),
and the full ``migrate_events`` / ``migrate_all_events`` flows against an
event store, including dry-run mode.

The framework keys migrations by ``type(event).__name__``, so the versioned
event classes below all carry the same class name (``UserCreated``), which
is how versioned event types are represented.
"""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.events.messages.event import Event
from quadkit.events.schema.evolution import (
    SchemaEvolution,
    Upcaster,
)
from quadkit.events.schema.migration.migrator import SchemaMigrator
from quadkit.events.schema.migration.types import (
    MigrationConfig,
    MigrationStatus,
)
from quadkit.events.schema.models import EventSchema
from quadkit.events.schema.registry import SchemaRegistry
from quadkit.events.stores.memory import InMemoryEventStore


def _versioned_event_class(name: str, **fields: Any) -> type:
    """Build an event subclass; versions share the class name.

    Plain (non-dataclass) subclasses inherit Event's lenient ``__init__``
    — the same convention the rest of the suite uses — so the store can
    reconstruct events with extra stamped attributes.
    """
    namespace = dict(fields)
    return type(name, (Event,), namespace)


UserCreatedV1 = _versioned_event_class("UserCreated", full_name="Jane Doe")
UserCreatedV2 = _versioned_event_class("UserCreated", first_name="", last_name="")
UserCreatedV3 = _versioned_event_class(
    "UserCreated", first_name="", last_name="", normalized=False
)
assert UserCreatedV1 is not UserCreatedV2 is not UserCreatedV3
assert (
    UserCreatedV1.__name__
    == UserCreatedV2.__name__
    == UserCreatedV3.__name__
    == "UserCreated"
)


class V1ToV2(Upcaster):
    event_type = "UserCreated"
    source_version = 1
    target_version = 2

    async def upcast(self, data: dict[str, Any]) -> dict[str, Any]:
        name = data.pop("full_name", "")
        parts = name.split(" ", 1)
        data["first_name"] = parts[0]
        data["last_name"] = parts[1] if len(parts) > 1 else ""
        return data


class V2ToV3(Upcaster):
    event_type = "UserCreated"
    source_version = 2
    target_version = 3

    async def upcast(self, data: dict[str, Any]) -> dict[str, Any]:
        data["normalized"] = True
        return data


class _UpdatingStore:
    """In-memory event store that records update_event calls."""

    def __init__(self, inner: InMemoryEventStore) -> None:
        self._inner = inner
        self.updated: list[tuple[Event, Event]] = []

    async def stream_all(self, **kwargs: Any) -> Any:
        async for event in self._inner.stream_all(**kwargs):
            yield event

    async def update_event(self, old: Event, new: Event) -> None:
        self.updated.append((old, new))


def _registry_with_classes() -> SchemaRegistry:
    registry = SchemaRegistry()
    registry.register_event_class(UserCreatedV1, version=1)
    registry.register_event_class(UserCreatedV2, version=2)
    registry.register_event_class(UserCreatedV3, version=3)
    return registry


async def test_migration_paths_and_data_evolution() -> None:
    """Paths chain upcasters; missing downcasters yield no path."""
    registry = _registry_with_classes()
    evolution = SchemaEvolution(registry)
    evolution.register_upcaster(V1ToV2())
    evolution.register_upcaster(V2ToV3())

    same = await evolution.get_migration_path("UserCreated", 1, 1)
    assert same is not None
    assert same.steps == []

    two_steps = await evolution.get_migration_path("UserCreated", 1, 3)
    assert two_steps is not None
    assert len(two_steps.steps) == 2

    no_downcast = await evolution.get_migration_path("UserCreated", 2, 1)
    assert no_downcast is None

    # data-level migration chains both upcasters and keeps untouched keys
    result = await evolution.migrate_data(
        "UserCreated",
        {"full_name": "Jane Doe", "tenant": "acme"},
        1,
        3,
    )
    assert result["first_name"] == "Jane"
    assert result["last_name"] == "Doe"
    assert result["normalized"] is True
    assert result["tenant"] == "acme"
    assert "full_name" not in result

    with pytest.raises(ValueError, match="No migration path"):
        await evolution.migrate_data("UserCreated", {}, 3, 1)


async def test_migrate_event_stamps_target_version() -> None:
    """migrate_event builds the target class and stamps schema_version."""
    registry = _registry_with_classes()
    evolution = SchemaEvolution(registry)
    evolution.register_upcaster(V1ToV2())
    evolution.register_upcaster(V2ToV3())

    event = UserCreatedV1(full_name="Jane Doe")
    migrated = await evolution.migrate_event(event, 2)
    assert type(migrated) is UserCreatedV2
    assert migrated.schema_version == 2
    assert migrated.first_name == "Jane"
    assert migrated.last_name == "Doe"
    assert not hasattr(migrated, "full_name")

    # multi-step migration in one call
    migrated3 = await evolution.migrate_event(event, 3)
    assert type(migrated3) is UserCreatedV3
    assert migrated3.schema_version == 3
    assert migrated3.normalized is True


async def test_migrate_events_over_store_with_dry_run() -> None:
    """migrate_events migrates v1 events in the store; dry_run only counts."""
    inner = InMemoryEventStore()
    await inner.append("users", [UserCreatedV1(full_name="Jane Doe")])
    await inner.append("users", [UserCreatedV1(full_name="John Smith")])
    store = _UpdatingStore(inner)

    registry = _registry_with_classes()
    evolution = SchemaEvolution(registry)
    evolution.register_upcaster(V1ToV2())

    # dry run: counts events but writes nothing
    dry = SchemaMigrator(
        store, evolution, config=MigrationConfig(dry_run=True, backup_before=False)
    )
    result = await dry.migrate_events("UserCreated", target_version=2)
    assert result.status is MigrationStatus.COMPLETED
    assert result.total_events == 2
    assert result.total_migrated == 2
    assert result.total_errors == 0
    assert store.updated == []

    # real run: events are rewritten through the store
    migrator = SchemaMigrator(
        store, evolution, config=MigrationConfig(backup_before=False)
    )
    result = await migrator.migrate_events("UserCreated", target_version=2)
    assert result.status is MigrationStatus.COMPLETED
    assert result.total_migrated == 2
    assert len(store.updated) == 2
    for old, new in store.updated:
        assert type(old) is UserCreatedV1
        assert type(new) is UserCreatedV2
        assert new.schema_version == 2
    first_new = store.updated[0][1]
    assert first_new.first_name == "Jane"
    assert first_new.last_name == "Doe"


async def test_migrate_all_events_uses_schema_versions() -> None:
    """migrate_all_events targets the latest version from the schema store."""
    inner = InMemoryEventStore()
    await inner.append("users", [UserCreatedV1(full_name="Jane Doe")])
    store = _UpdatingStore(inner)

    registry = _registry_with_classes()
    await registry.register_schema(
        EventSchema(
            event_type="UserCreated",
            version=1,
            event_class=UserCreatedV1,
        )
    )
    await registry.register_schema(
        EventSchema(
            event_type="UserCreated",
            version=2,
            event_class=UserCreatedV2,
        )
    )
    assert await registry.get_latest_version("UserCreated") == 2

    evolution = SchemaEvolution(registry)
    evolution.register_upcaster(V1ToV2())

    migrator = SchemaMigrator(
        store, evolution, config=MigrationConfig(backup_before=False)
    )
    result = await migrator.migrate_all_events()
    assert result.status is MigrationStatus.COMPLETED
    assert result.total_events == 1
    assert result.total_migrated == 1
    assert len(store.updated) == 1
    assert type(store.updated[0][1]) is UserCreatedV2
