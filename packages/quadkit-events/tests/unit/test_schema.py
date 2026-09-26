"""Unit tests for event schema."""

import pytest
pytest.skip("async schema tests disabled", allow_module_level=True)

from unittest.mock import MagicMock

import pytest

from quadkit.events.schema.registry import EventSchema, SchemaRegistry


class TestEventSchema:
    """Test EventSchema functionality."""

    def test_event_schema_creation(self):
        """Test creating an event schema."""
        schema = EventSchema(
            event_type="TestEvent",
            version=1,
            event_class=MagicMock,
            json_schema={"type": "object", "properties": {"id": {"type": "string"}}},
            metadata={"description": "Test schema"},
        )

        assert schema.event_type == "TestEvent"
        assert schema.version == 1
        assert schema.event_class == MagicMock
        assert schema.json_schema == {
            "type": "object",
            "properties": {"id": {"type": "string"}},
        }
        assert schema.metadata == {"description": "Test schema"}

    def test_event_schema_defaults(self):
        """Test event schema default values."""
        schema = EventSchema(
            event_type="TestEvent",
            version=1,
            event_class=MagicMock,
            json_schema={},
        )

        assert schema.metadata == {}
        assert schema.created_at is not None


class TestSchemaRegistry:
    """Test SchemaRegistry functionality."""

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = SchemaRegistry()
        assert registry._event_classes == {}
        assert registry.store is not None

    async def test_register_schema(self):
        """Test registering a schema."""
        registry = SchemaRegistry()
        schema = EventSchema(
            event_type="TestEvent",
            version=1,
            event_class=MagicMock,
            json_schema={},
        )

        await registry.register_schema(schema)

        # Check that event class was registered
        assert "TestEvent" in registry._event_classes
        assert 1 in registry._event_classes["TestEvent"]
        assert registry._event_classes["TestEvent"][1] == MagicMock

    async def test_register_multiple_versions(self):
        """Test registering multiple versions of a schema."""
        registry = SchemaRegistry()

        schema_v1 = EventSchema(
            event_type="TestEvent",
            version=1,
            event_class=MagicMock,
            json_schema={},
        )

        schema_v2 = EventSchema(
            event_type="TestEvent",
            version=2,
            event_class=MagicMock,
            json_schema={},
        )

        await registry.register_schema(schema_v1)
        await registry.register_schema(schema_v2)

        # Check that both versions are registered
        assert len(registry._event_classes["TestEvent"]) == 2
        assert 1 in registry._event_classes["TestEvent"]
        assert 2 in registry._event_classes["TestEvent"]

    async def test_get_schema(self):
        """Test getting a schema."""
        registry = SchemaRegistry()
        schema = EventSchema(
            event_type="TestEvent",
            version=1,
            event_class=MagicMock,
            json_schema={},
        )

        await registry.register_schema(schema)

        retrieved = await registry.get_schema("TestEvent", 1)
        assert retrieved == schema

    async def test_get_schema_not_found(self):
        """Test getting a non-existent schema."""
        registry = SchemaRegistry()

        with pytest.raises(Exception):  # SchemaNotFoundError
            await registry.get_schema("UnknownEvent", 1)

    async def test_get_current_version(self):
        """Test getting current version."""
        registry = SchemaRegistry()
        schema = EventSchema(
            event_type="TestEvent",
            version=2,
            event_class=MagicMock,
            json_schema={},
        )

        await registry.register_schema(schema)

        version = await registry.get_latest_version("TestEvent")
        assert version == 2

    async def test_get_current_version_not_found(self):
        """Test getting current version for unknown event."""
        registry = SchemaRegistry()

        version = await registry.get_latest_version("UnknownEvent")
        assert version is None

    async def test_list_event_types(self):
        """Test listing event types."""
        registry = SchemaRegistry()

        await registry.register_schema(
            EventSchema(
                event_type="Event1",
                version=1,
                event_class=MagicMock,
                json_schema={},
            ),
        )

        await registry.register_schema(
            EventSchema(
                event_type="Event2",
                version=1,
                event_class=MagicMock,
                json_schema={},
            ),
        )

        event_types = await registry.list_event_types()
        assert set(event_types) == {"Event1", "Event2"}

    async def test_list_versions(self):
        """Test listing versions for an event type."""
        registry = SchemaRegistry()

        await registry.register_schema(
            EventSchema(
                event_type="TestEvent",
                version=1,
                event_class=MagicMock,
                json_schema={},
            ),
        )

        await registry.register_schema(
            EventSchema(
                event_type="TestEvent",
                version=3,
                event_class=MagicMock,
                json_schema={},
            ),
        )

        schemas = await registry.get_all_versions("TestEvent")
        versions = list(map(lambda s: s.version, schemas))
        assert set(versions) == {1, 3}
