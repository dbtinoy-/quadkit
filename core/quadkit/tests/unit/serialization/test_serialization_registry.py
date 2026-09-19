"""Tests for serialization/registry module."""
import pytest

from quadkit.result import Ok, Err
from quadkit.serialization.registry import SerializerRegistry
from quadkit.serialization.exceptions import NegotiationError


class MockSerializer:
    """Mock serializer for testing."""

    def serialize(self, obj: object) -> bytes:
        return b"mock"

    def deserialize(self, data: bytes, type_: type) -> object:
        return object()


class TestSerializerRegistryCreation:
    """Tests for creating SerializerRegistry."""

    def test_empty_registry(self) -> None:
        """Test creating empty registry."""
        registry = SerializerRegistry()
        assert registry._serializers == {}

    def test_initial_serializers_empty(self) -> None:
        """Test that serializers dict starts empty."""
        registry = SerializerRegistry()
        assert len(registry._serializers) == 0


class TestSerializerRegistryRegister:
    """Tests for register method."""

    def test_register_serializer(self) -> None:
        """Test registering a serializer."""
        registry = SerializerRegistry()
        serializer = MockSerializer()
        registry.register("application/json", serializer)
        assert "application/json" in registry._serializers

    def test_register_normalizes_content_type(self) -> None:
        """Test that content type is lowercased."""
        registry = SerializerRegistry()
        serializer = MockSerializer()
        registry.register("Application/JSON", serializer)
        assert "application/json" in registry._serializers

    def test_register_multiple_serializers(self) -> None:
        """Test registering multiple serializers."""
        registry = SerializerRegistry()
        json_serializer = MockSerializer()
        xml_serializer = MockSerializer()
        registry.register("application/json", json_serializer)
        registry.register("application/xml", xml_serializer)
        assert len(registry._serializers) == 2


class TestSerializerRegistryGet:
    """Tests for get method."""

    def test_get_existing(self) -> None:
        """Test getting existing serializer."""
        registry = SerializerRegistry()
        serializer = MockSerializer()
        registry.register("application/json", serializer)
        result = registry.get("application/json")
        assert result is serializer

    def test_get_nonexistent(self) -> None:
        """Test getting non-existent serializer returns None."""
        registry = SerializerRegistry()
        result = registry.get("application/json")
        assert result is None

    def test_get_normalizes_content_type(self) -> None:
        """Test that get normalizes content type."""
        registry = SerializerRegistry()
        serializer = MockSerializer()
        registry.register("application/json", serializer)
        result = registry.get("Application/JSON")
        assert result is serializer


class TestSerializerRegistryNegotiate:
    """Tests for negotiate method."""

    def test_negotiate_empty_accept_returns_json(self) -> None:
        """Test empty accept header returns JSON serializer."""
        registry = SerializerRegistry()
        serializer = MockSerializer()
        registry.register("application/json", serializer)
        result = registry.negotiate("")
        assert result.is_ok()
        assert result.unwrap() is serializer

    def test_negotiate_no_serializers_returns_err(self) -> None:
        """Test negotiate with no serializers returns error."""
        registry = SerializerRegistry()
        result = registry.negotiate("")
        assert result.is_err()

    def test_negotiate_exact_match(self) -> None:
        """Test negotiate with exact Accept match."""
        registry = SerializerRegistry()
        serializer = MockSerializer()
        registry.register("application/json", serializer)
        result = registry.negotiate("application/json")
        assert result.is_ok()
        assert result.unwrap() is serializer

    def test_negotiate_wildcard(self) -> None:
        """Test negotiate with wildcard Accept."""
        registry = SerializerRegistry()
        serializer = MockSerializer()
        registry.register("application/json", serializer)
        result = registry.negotiate("*/*")
        assert result.is_ok()
        assert result.unwrap() is serializer

    def test_negotiate_multiple_types(self) -> None:
        """Test negotiate with multiple Accept types."""
        registry = SerializerRegistry()
        json_serializer = MockSerializer()
        xml_serializer = MockSerializer()
        registry.register("application/json", json_serializer)
        registry.register("application/xml", xml_serializer)
        result = registry.negotiate("application/xml, application/json")
        assert result.is_ok()

    def test_negotiate_no_match_returns_err(self) -> None:
        """Test negotiate with no matching serializer."""
        registry = SerializerRegistry()
        # No serializers registered at all
        result = registry.negotiate("application/xml")
        assert result.is_err()

    def test_negotiate_default_fallback(self) -> None:
        """Test negotiate falls back to JSON."""
        registry = SerializerRegistry()
        json_serializer = MockSerializer()
        registry.register("application/json", json_serializer)
        result = registry.negotiate("text/plain")
        assert result.is_ok()
        assert result.unwrap() is json_serializer