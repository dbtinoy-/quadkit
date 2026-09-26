"""Schema evolution for event versioning.

This module provides tools for evolving event schemas, including
upcasters for migrating events between versions.

Example:
    ```python
    from quadkit.events.schema import SchemaEvolution, Upcaster

    # Define upcaster
    class UserCreatedV1ToV2(Upcaster):
        event_type = "UserCreated"
        source_version = 1
        target_version = 2

        async def upcast(self, data: dict) -> dict:
            # Add new field with default
            data["display_name"] = data.get("username", "")
            return data

    # Setup evolution
    evolution = SchemaEvolution(registry)
    evolution.register_upcaster(UserCreatedV1ToV2())

    # Migrate event
    migrated = await evolution.migrate_event(event, target_version=2)
    ```
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.events.messages.event import Event
    from quadkit.events.schema.registry import SchemaRegistry


class Upcaster(ABC):
    """Base class for event upcasters.

    An upcaster transforms event data from one version to a newer version.

    Example:
        ```python
        class OrderV1ToV2(Upcaster):
            event_type = "OrderCreated"
            source_version = 1
            target_version = 2

            async def upcast(self, data: dict) -> dict:
                # Split name into first/last
                name = data.pop("customer_name", "")
                parts = name.split(" ", 1)
                data["first_name"] = parts[0]
                data["last_name"] = parts[1] if len(parts) > 1 else ""
                return data
        ```
    """

    event_type: str
    source_version: int
    target_version: int

    @abstractmethod
    async def upcast(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform event data to newer version.

        Args:
            data: Event data in source version format.

        Returns:
            Event data in target version format.
        """
        ...


class Downcaster(ABC):
    """Base class for event downcasters.

    A downcaster transforms event data from one version to an older version.
    This is useful for backwards compatibility but may lose information.

    Example:
        ```python
        class OrderV2ToV1(Downcaster):
            event_type = "OrderCreated"
            source_version = 2
            target_version = 1

            async def downcast(self, data: dict) -> dict:
                # Combine first/last name
                first = data.pop("first_name", "")
                last = data.pop("last_name", "")
                data["customer_name"] = f"{first} {last}".strip()
                return data
        ```
    """

    event_type: str
    source_version: int
    target_version: int

    @abstractmethod
    async def downcast(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform event data to older version.

        Args:
            data: Event data in source version format.

        Returns:
            Event data in target version format.
        """
        ...


@dataclass
class MigrationPath:
    """Represents a path for migrating between versions.

    Attributes:
        event_type: Event type name.
        from_version: Starting version.
        to_version: Target version.
        steps: List of upcasters/downcasters to apply.
    """

    event_type: str
    from_version: int
    to_version: int
    steps: list[Upcaster | Downcaster]


class SchemaEvolution:
    """Handles event schema evolution and migration.

    This class manages upcasters and downcasters for evolving events
    between schema versions.

    Example:
        ```python
        evolution = SchemaEvolution(registry)

        # Register upcasters
        evolution.register_upcaster(UserV1ToV2())
        evolution.register_upcaster(UserV2ToV3())

        # Migrate event from v1 to v3
        event_v3 = await evolution.migrate_event(event_v1, target_version=3)

        # Or get migration path
        path = await evolution.get_migration_path("UserCreated", 1, 3)
        ```
    """

    def __init__(self, registry: SchemaRegistry) -> None:
        """Initialize schema evolution.

        Args:
            registry: Schema registry for schema lookup.
        """
        self.registry = registry
        self._upcasters: dict[str, dict[tuple[int, int], Upcaster]] = {}
        self._downcasters: dict[str, dict[tuple[int, int], Downcaster]] = {}

    def register_upcaster(self, upcaster: Upcaster) -> None:
        """Register an upcaster.

        Args:
            upcaster: The upcaster to register.
        """
        event_type = upcaster.event_type
        if event_type not in self._upcasters:
            self._upcasters[event_type] = {}

        key = (upcaster.source_version, upcaster.target_version)
        self._upcasters[event_type][key] = upcaster

    def register_downcaster(self, downcaster: Downcaster) -> None:
        """Register a downcaster.

        Args:
            downcaster: The downcaster to register.
        """
        event_type = downcaster.event_type
        if event_type not in self._downcasters:
            self._downcasters[event_type] = {}

        key = (downcaster.source_version, downcaster.target_version)
        self._downcasters[event_type][key] = downcaster

    async def get_migration_path(
        self,
        event_type: str,
        from_version: int,
        to_version: int,
    ) -> MigrationPath | None:
        """Get the migration path between versions.

        Args:
            event_type: Event type name.
            from_version: Starting version.
            to_version: Target version.

        Returns:
            MigrationPath or None if no path exists.
        """
        if from_version == to_version:
            return MigrationPath(
                event_type=event_type,
                from_version=from_version,
                to_version=to_version,
                steps=[],
            )

        steps: list[Upcaster | Downcaster] = []
        is_upgrade = to_version > from_version

        if is_upgrade:
            # Find upcasters
            current = from_version
            while current < to_version:
                upcaster = self._find_upcaster(event_type, current)
                if upcaster is None:
                    return None  # No path
                steps.append(upcaster)
                current = upcaster.target_version
        else:
            # Find downcasters
            current = from_version
            while current > to_version:
                downcaster = self._find_downcaster(event_type, current)
                if downcaster is None:
                    return None  # No path
                steps.append(downcaster)
                current = downcaster.target_version

        return MigrationPath(
            event_type=event_type,
            from_version=from_version,
            to_version=to_version,
            steps=steps,
        )

    def _find_upcaster(self, event_type: str, from_version: int) -> Upcaster | None:
        """Find an upcaster from a specific version."""
        if event_type not in self._upcasters:
            return None

        for (source, _), upcaster in self._upcasters[event_type].items():
            if source == from_version:
                return upcaster
        return None

    def _find_downcaster(self, event_type: str, from_version: int) -> Downcaster | None:
        """Find a downcaster from a specific version."""
        if event_type not in self._downcasters:
            return None

        for (source, _), downcaster in self._downcasters[event_type].items():
            if source == from_version:
                return downcaster
        return None

    async def migrate_data(
        self,
        event_type: str,
        data: dict[str, Any],
        from_version: int,
        to_version: int,
    ) -> dict[str, Any]:
        """Migrate event data between versions.

        Args:
            event_type: Event type name.
            data: Event data to migrate.
            from_version: Current version.
            to_version: Target version.

        Returns:
            Migrated event data.

        Raises:
            ValueError: If no migration path exists.
        """
        if from_version == to_version:
            return data

        path = await self.get_migration_path(event_type, from_version, to_version)
        if path is None:
            raise ValueError(
                f"No migration path from {event_type} v{from_version} to v{to_version}",
            )

        result = dict(data)
        for step in path.steps:
            if isinstance(step, Upcaster):
                result = await step.upcast(result)
            else:
                result = await step.downcast(result)

        return result

    async def migrate_event(
        self,
        event: Event,
        target_version: int,
    ) -> Event:
        """Migrate an event to a target version.

        Args:
            event: Event to migrate.
            target_version: Target schema version.

        Returns:
            New event instance at target version.

        Raises:
            ValueError: If migration fails.
        """
        event_type = type(event).__name__
        current_version = getattr(event, "schema_version", 1)

        if current_version == target_version:
            return event

        # Get event data
        if hasattr(event, "model_dump"):
            data = event.model_dump(mode="json")
        else:
            data = dict(getattr(event, "__dict__", {}))

        # Migrate data
        migrated_data = await self.migrate_data(
            event_type,
            data,
            current_version,
            target_version,
        )
        # Stamp the target version — the source data dict still carries
        # the old ``schema_version`` and would otherwise be propagated to
        # the migrated instance.
        migrated_data["schema_version"] = target_version

        # Get target event class
        event_class = await self.registry.get_event_class(event_type, target_version)
        if event_class is None:
            raise ValueError(
                f"No event class registered for {event_type} v{target_version}",
            )

        # Create new event instance
        from typing import cast

        if hasattr(event_class, "model_validate"):
            return cast("Event", event_class.model_validate(migrated_data))
        return cast("Event", event_class(**migrated_data))


class EventMigrator:
    """Utility for batch event migration.

    This class provides tools for migrating multiple events
    to their latest schema versions.

    Example:
        ```python
        migrator = EventMigrator(evolution)

        # Migrate all events to latest
        migrated = await migrator.migrate_to_latest(events)

        # Migrate to specific versions
        version_map = {"UserCreated": 3, "OrderCreated": 2}
        migrated = await migrator.migrate_to_versions(events, version_map)
        ```
    """

    def __init__(self, evolution: SchemaEvolution) -> None:
        """Initialize event migrator.

        Args:
            evolution: Schema evolution instance.
        """
        self.evolution = evolution

    async def migrate_to_latest(
        self,
        events: list[Event],
    ) -> list[Event]:
        """Migrate all events to their latest schema versions.

        Args:
            events: Events to migrate.

        Returns:
            List of migrated events.
        """
        migrated = []
        for event in events:
            event_type = type(event).__name__
            latest = await self.evolution.registry.get_latest_version(event_type)
            if latest:
                migrated_event = await self.evolution.migrate_event(event, latest)
                migrated.append(migrated_event)
            else:
                migrated.append(event)
        return migrated

    async def migrate_to_versions(
        self,
        events: list[Event],
        version_map: dict[str, int],
    ) -> list[Event]:
        """Migrate events to specific versions.

        Args:
            events: Events to migrate.
            version_map: Mapping of event type to target version.

        Returns:
            List of migrated events.
        """
        migrated = []
        for event in events:
            event_type = type(event).__name__
            target_version = version_map.get(event_type)
            if target_version:
                migrated_event = await self.evolution.migrate_event(
                    event,
                    target_version,
                )
                migrated.append(migrated_event)
            else:
                migrated.append(event)
        return migrated

    async def get_migration_report(
        self,
        events: list[Event],
    ) -> dict[str, Any]:
        """Generate a report of events needing migration.

        Args:
            events: Events to analyze.

        Returns:
            Report dictionary.
        """
        report: dict[str, Any] = {
            "total_events": len(events),
            "events_by_type": {},
            "needs_migration": [],
        }

        for event in events:
            event_type = type(event).__name__
            current_version = getattr(event, "schema_version", 1)
            latest = await self.evolution.registry.get_latest_version(event_type)

            if event_type not in report["events_by_type"]:
                report["events_by_type"][event_type] = {
                    "count": 0,
                    "versions": {},
                    "latest_version": latest,
                }

            report["events_by_type"][event_type]["count"] += 1

            version_key = str(current_version)
            if version_key not in report["events_by_type"][event_type]["versions"]:
                report["events_by_type"][event_type]["versions"][version_key] = 0
            report["events_by_type"][event_type]["versions"][version_key] += 1

            if latest and current_version < latest:
                report["needs_migration"].append(
                    {
                        "event_type": event_type,
                        "current_version": current_version,
                        "latest_version": latest,
                    },
                )

        return report
