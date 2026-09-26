"""Unit tests for IdentityMap and EntitySnapshot (unit_of_work/identity_map.py)."""

from __future__ import annotations

from typing import Any

from quadkit.sql.unit_of_work.identity_map import (
    EntitySnapshot,
    IdentityMap,
)


class _Entity:
    def __init__(self, **state: Any) -> None:
        self.__dict__.update(state)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


class TestEntitySnapshot:
    def test_detect_changes_reports_only_modified_fields(self) -> None:
        entity = _Entity(name="Alice", age=30, city="Pasig")
        snapshot = EntitySnapshot.from_entity(entity, "users", 1)
        assert snapshot.detect_changes(entity) == []

        entity.name = "Bob"
        entity.age = 31
        changes = snapshot.detect_changes(entity)
        assert {c.field_name for c in changes} == {"name", "age"}
        by_name = {c.field_name: (c.old_value, c.new_value) for c in changes}
        assert by_name["name"] == ("Alice", "Bob")
        assert by_name["age"] == (30, 31)

    def test_from_entity_deep_copies_state(self) -> None:
        entity = _Entity(tags=["a"])
        snapshot = EntitySnapshot.from_entity(entity, "t", 1)
        entity.tags.append("b")
        assert snapshot.state["tags"] == ["a"]

    def test_extract_state_prefers_to_dict(self) -> None:
        class Obj:
            def to_dict(self) -> dict[str, Any]:
                return {"x": 1}

        assert EntitySnapshot._extract_state(Obj()) == {"x": 1}

    def test_extract_state_falls_back_to_dict(self) -> None:
        class Plain:
            def __init__(self) -> None:
                self.public = 1
                self._private = 2
                self.other = 3

        assert EntitySnapshot._extract_state(Plain()) == {"public": 1, "other": 3}

    def test_extract_state_without_dict_or_to_dict(self) -> None:
        class Frozen:
            __slots__ = ("x",)

        assert EntitySnapshot._extract_state(Frozen()) == {}


class TestIdentityMap:
    def test_track_get_is_tracked(self) -> None:
        im = IdentityMap()
        entity = _Entity(id=1)
        im.track(entity, "users", 1)
        assert im.get("users", 1) is entity
        assert im.is_tracked("users", 1)
        assert im.get("users", 2) is None
        assert not im.is_tracked("users", 2)

    def test_retrack_same_key_is_lru_fresh(self) -> None:
        im = IdentityMap(max_entries=2)
        e1, e2, e3 = _Entity(id=1), _Entity(id=2), _Entity(id=3)
        im.track(e1, "t", 1)
        im.track(e2, "t", 2)
        im.track(e3, "t", 3)  # evicts key 1
        assert not im.is_tracked("t", 1)
        assert im.get("t", 2) is e2 and im.get("t", 3) is e3

        # Re-tracking key 2 refreshes it, so key 3 becomes the eviction victim.
        im.track(e2, "t", 2)
        im.track(e1, "t", 4)
        assert im.is_tracked("t", 2)
        assert not im.is_tracked("t", 3)

    def test_unlimited_when_max_entries_zero(self) -> None:
        im = IdentityMap(max_entries=0)
        for i in range(50):
            im.track(_Entity(id=i), "t", i)
        assert im.get_stats()["tracked_entities"] == 50

    def test_get_snapshot_returns_original_state(self) -> None:
        im = IdentityMap()
        entity = _Entity(name="A")
        im.track(entity, "t", 1)
        snapshot = im.get_snapshot("t", 1)
        assert snapshot is not None
        entity.name = "B"
        assert snapshot.state["name"] == "A"
        assert im.get_snapshot("t", 99) is None

    def test_detect_all_changes_reports_only_dirty(self) -> None:
        im = IdentityMap()
        clean = _Entity(name="same")
        dirty = _Entity(name="old")
        im.track(clean, "t", 1)
        im.track(dirty, "t", 2)
        dirty.name = "new"
        result = im.detect_all_changes()
        assert [(t, k) for t, k, _ in result] == [("t", 2)]
        assert result[0][2][0].new_value == "new"

    def test_untrack_and_clear(self) -> None:
        im = IdentityMap()
        im.track(_Entity(), "t", 1)
        im.untrack("t", 1)
        assert not im.is_tracked("t", 1)
        assert im.get_snapshot("t", 1) is None
        im.track(_Entity(), "t", 2)
        im.clear()
        assert im.get_stats() == {
            "tracked_entities": 0,
            "snapshots": 0,
            "max_entries": 1000,
        }

    def test_clear_clean_removes_only_clean_entities(self) -> None:
        im = IdentityMap()
        clean = _Entity(name="c")
        dirty = _Entity(name="old")
        im.track(clean, "t", 1)
        im.track(dirty, "t", 2)
        dirty.name = "new"
        removed = im.clear_clean()
        assert removed == 1
        assert im.is_tracked("t", 2)
        assert not im.is_tracked("t", 1)
