"""Identity Map and Entity Snapshot for dirty tracking.

The IdentityMap tracks entities loaded within a Unit of Work scope,
ensuring that the same database row maps to the same Python object.
EntitySnapshot captures the initial state for automatic change detection.

Example:
    identity_map = IdentityMap()
    identity_map.track(user, "users", user.id)

    # Later:
    snapshot = identity_map.get_snapshot("users", user.id)
    changes = snapshot.detect_changes(user)
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, cast


@dataclass
class EntityChange:
    """Represents a detected change to an entity field."""

    field_name: str
    old_value: Any
    new_value: Any


@dataclass
class EntitySnapshot:
    """Snapshot of an entity's state at a point in time.

    Used for dirty tracking — detecting which fields have changed
    since the entity was loaded.
    """

    table: str
    key: Any
    state: dict[str, Any]
    entity_ref: Any = None  # Weak reference to the actual entity

    def detect_changes(self, entity: Any) -> list[EntityChange]:
        """Compare current entity state against the snapshot.

        Args:
            entity: The entity to compare against.

        Returns:
            List of detected changes.
        """
        changes: list[EntityChange] = []

        current_state = self._extract_state(entity)
        for field_name, old_value in self.state.items():
            new_value = current_state.get(field_name)
            if old_value != new_value:
                changes.append(
                    EntityChange(field_name, old_value, new_value),
                )

        return changes

    @staticmethod
    def _extract_state(entity: Any) -> dict[str, Any]:
        """Extract serializable state from an entity."""
        if hasattr(entity, "to_dict"):
            return cast("dict[str, Any]", entity.to_dict())
        if hasattr(entity, "__dict__"):
            return {k: v for k, v in entity.__dict__.items() if not k.startswith("_")}
        return {}

    @classmethod
    def from_entity(
        cls,
        entity: Any,
        table: str,
        key: Any,
    ) -> EntitySnapshot:
        """Create a snapshot from an entity's current state."""
        state = cls._extract_state(entity)
        return cls(
            table=table,
            key=key,
            state=copy.deepcopy(state),
            entity_ref=entity,
        )


class IdentityMap:
    """Tracks entities loaded within a Unit of Work scope.

    Ensures that the same database row always maps to the same
    Python object instance within a single UoW.

    Args:
        max_entries: Maximum number of entities to track before LRU eviction
            kicks in.  ``0`` means unlimited (legacy behaviour; not recommended
            for long-lived UoW scopes).  Default is ``1000``.
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self._max_entries = max_entries
        # OrderedDict maintains insertion order; used for O(1) LRU eviction.
        self._entities: dict[tuple[str, Any], Any] = {}
        self._snapshots: dict[tuple[str, Any], EntitySnapshot] = {}

    def track(self, entity: Any, table: str, key: Any) -> None:
        """Register an entity in the identity map.

        When ``max_entries`` is exceeded the *oldest* entry (LRU) is evicted
        before the new entity is inserted.

        Args:
            entity: The entity instance to track.
            table: The table/collection name.
            key: The primary key value.
        """
        map_key = (table, key)
        if map_key in self._entities:
            # Re-tracking an existing key; move to end (most-recently used).
            self._entities.pop(map_key)
            self._snapshots.pop(map_key, None)

        if self._max_entries > 0 and len(self._entities) >= self._max_entries:
            # Evict the oldest (least-recently-used) entry.
            oldest_key = next(iter(self._entities))
            self._entities.pop(oldest_key)
            self._snapshots.pop(oldest_key, None)

        self._entities[map_key] = entity
        self._snapshots[map_key] = EntitySnapshot.from_entity(
            entity,
            table,
            key,
        )

    def get(self, table: str, key: Any) -> Any | None:
        """Retrieve a tracked entity by table and key."""
        return self._entities.get((table, key))

    def is_tracked(self, table: str, key: Any) -> bool:
        """Check if an entity is tracked."""
        return (table, key) in self._entities

    def get_snapshot(self, table: str, key: Any) -> EntitySnapshot | None:
        """Get the original snapshot for a tracked entity."""
        return self._snapshots.get((table, key))

    def detect_all_changes(self) -> list[tuple[str, Any, list[EntityChange]]]:
        """Detect changes across all tracked entities.

        Returns:
            List of (table, key, changes) tuples for entities with changes.
        """
        dirty: list[tuple[str, Any, list[EntityChange]]] = []

        for (table, key), snapshot in self._snapshots.items():
            entity = self._entities.get((table, key))
            if entity is None:
                continue

            changes = snapshot.detect_changes(entity)
            if changes:
                dirty.append((table, key, changes))

        return dirty

    def untrack(self, table: str, key: Any) -> None:
        """Remove an entity from the identity map."""
        map_key = (table, key)
        self._entities.pop(map_key, None)
        self._snapshots.pop(map_key, None)

    def clear(self) -> None:
        """Clear all tracked entities and snapshots."""
        self._entities.clear()
        self._snapshots.clear()

    def clear_clean(self) -> int:
        """Remove entities that have no pending changes (clean entities).

        Releases memory for entities that match their snapshot exactly.
        Dirty entities (with pending changes) are retained so they can still
        be flushed.

        Returns:
            Number of clean entities that were removed.
        """
        clean_keys = [
            map_key
            for map_key, snapshot in self._snapshots.items()
            if not snapshot.detect_changes(self._entities[map_key])
        ]
        for map_key in clean_keys:
            self._entities.pop(map_key)
            self._snapshots.pop(map_key)
        return len(clean_keys)

    def get_stats(self) -> dict[str, int]:
        """Get identity map statistics."""
        return {
            "tracked_entities": len(self._entities),
            "snapshots": len(self._snapshots),
            "max_entries": self._max_entries,
        }
