"""Schema registry for event versioning."""

from __future__ import annotations

from typing import Any

from quadkit.events.schema.models import (
    EventSchema,
    SchemaIncompatibleError,
    SchemaNotFoundError,
)
from quadkit.events.schema.store import InMemorySchemaStore, SchemaStore
from quadkit.primitives.registry import Registry


class SchemaRegistry:
    """Central registry for managing event schemas.

    The schema registry provides:
    - Version tracking for event schemas
    - Compatibility checking between versions
    - Event type discovery and validation

    Uses an internal :class:`Registry` for the event-class mapping
    to benefit from unified introspection.
    """

    def __init__(
        self,
        store: SchemaStore | None = None,
        enforce_compatibility: bool = True,
    ) -> None:
        """Initialize the schema registry.

        Args:
            store: Schema store for persistence.
            enforce_compatibility: Whether to check compatibility.
        """
        self.store = store or InMemorySchemaStore()
        self.enforce_compatibility = enforce_compatibility
        self._event_classes: Registry[str, dict[int, type]] = Registry(
            name="events.schema_classes",
            allow_overwrite=True,
        )

    async def register_schema(
        self,
        schema: EventSchema,
        check_compatibility: bool | None = None,
    ) -> None:
        """Register a new event schema.

        Args:
            schema: Schema to register.
            check_compatibility: Override compatibility check.

        Raises:
            SchemaIncompatibleError: If not compatible with previous version.
        """
        should_check = (
            check_compatibility
            if check_compatibility is not None
            else self.enforce_compatibility
        )

        # Check compatibility with previous version
        if should_check and schema.version > 1:
            prev_schema = await self.store.get(schema.event_type, schema.version - 1)
            if prev_schema:
                is_compatible, issues = schema.is_compatible_with(prev_schema)
                if not is_compatible:
                    raise SchemaIncompatibleError(
                        f"Schema v{schema.version} not compatible with "
                        f"v{schema.version - 1}",
                        event_type=schema.event_type,
                        version=schema.version,
                        issues=issues,
                    )

        await self.store.save(schema)

        # Register event class
        if schema.event_class:
            versions = self._event_classes.get(schema.event_type)
            if versions is None:
                versions = {}
                self._event_classes.register(schema.event_type, versions)
            versions[schema.version] = schema.event_class

    async def get_schema(
        self,
        event_type: str,
        version: int | None = None,
    ) -> EventSchema:
        """Get a schema by event type and version.

        Args:
            event_type: Event type name.
            version: Schema version (None for latest).

        Returns:
            The schema.

        Raises:
            SchemaNotFoundError: If schema not found.
        """
        if version is None:
            schema = await self.store.get_latest(event_type)
        else:
            schema = await self.store.get(event_type, version)

        if schema is None:
            raise SchemaNotFoundError(event_type, version)

        return schema

    async def get_event_class(
        self,
        event_type: str,
        version: int | None = None,
    ) -> type | None:
        """Get the event class for a schema.

        Args:
            event_type: Event type name.
            version: Schema version (None for latest).

        Returns:
            The event class or None.
        """
        versions = self._event_classes.get(event_type)

        if not versions:
            return None

        if version is None:
            return versions[max(versions.keys())]

        return versions.get(version)

    async def validate(
        self,
        event_type: str,
        data: dict[str, Any],
        version: int | None = None,
    ) -> tuple[bool, list[str]]:
        """Validate data against a schema.

        Args:
            event_type: Event type name.
            data: Data to validate.
            version: Schema version (None for latest).

        Returns:
            Tuple of (is_valid, list of errors).
        """
        try:
            schema = await self.get_schema(event_type, version)
            return schema.validate(data)
        except SchemaNotFoundError:
            return True, []  # No schema = no validation

    async def list_event_types(self) -> list[str]:
        """List all registered event types.

        Returns:
            List of event type names.
        """
        return await self.store.list_event_types()

    async def get_all_versions(self, event_type: str) -> list[EventSchema]:
        """Get all versions of an event type.

        Args:
            event_type: Event type name.

        Returns:
            List of all schema versions.
        """
        return await self.store.get_all_versions(event_type)

    async def get_latest_version(self, event_type: str) -> int | None:
        """Get the latest version number for an event type.

        Args:
            event_type: Event type name.

        Returns:
            Latest version number or None.
        """
        schema = await self.store.get_latest(event_type)
        return schema.version if schema else None

    def register_event_class(
        self,
        event_class: type,
        event_type: str | None = None,
        version: int = 1,
    ) -> None:
        """Register an event class without a full schema.

        Args:
            event_class: The event class.
            event_type: Event type name (default: class name).
            version: Version number.
        """
        event_type = event_type or event_class.__name__
        versions = self._event_classes.get(event_type)
        if versions is None:
            versions = {}
            self._event_classes.register(event_type, versions)
        versions[version] = event_class
