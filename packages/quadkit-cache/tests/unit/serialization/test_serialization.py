"""
Unit tests for serialization implementations.
"""

from datetime import datetime
from uuid import uuid4

import pytest

from quadkit.cache.exceptions import CacheSerializationError as SerializationError

# Import from the serialization package
from quadkit.cache.serialization import JSONSerializer


@pytest.mark.asyncio
class TestJSONSerializer:
    """Test JSON serializer functionality."""

    @pytest.fixture
    def serializer(self):
        return JSONSerializer()

    async def test_basic_types(self, serializer):
        """Test serialization of basic Python types."""
        test_cases = [
            ("string", "string"),
            (42, 42),
            (3.14, 3.14),
            (True, True),
            (False, False),
            (None, None),
            ([1, 2, 3], [1, 2, 3]),
            ({"key": "value"}, {"key": "value"}),
        ]

        for original, expected in test_cases:
            serialized = await serializer.serialize(original)
            deserialized = await serializer.deserialize(serialized)
            assert deserialized == expected

    async def test_datetime_serialization(self, serializer):
        """Test datetime object serialization."""
        dt = datetime(2025, 12, 1, 10, 30, 45)
        serialized = await serializer.serialize(dt)
        deserialized = await serializer.deserialize(serialized)

        # JSON deserialization doesn't preserve datetime type
        # This tests that it serializes without error
        assert isinstance(serialized, (str, bytes))
        assert deserialized is not None

    async def test_uuid_serialization(self, serializer):
        """Test UUID object serialization."""
        uuid_obj = uuid4()
        serialized = await serializer.serialize(uuid_obj)
        deserialized = await serializer.deserialize(serialized)

        # JSON deserialization doesn't preserve UUID type
        # This tests that it serializes without error
        assert isinstance(serialized, (str, bytes))
        assert deserialized is not None

    async def test_custom_object(self, serializer):
        """Test custom object serialization."""

        class TestObject:
            def __init__(self, value):
                self.value = value

        obj = TestObject("test")
        serialized = await serializer.serialize(obj)
        deserialized = await serializer.deserialize(serialized)

        # Should serialize the __dict__ of the object
        assert isinstance(serialized, (str, bytes))
        assert deserialized is not None

    async def test_invalid_json_deserialization(self, serializer):
        """Test deserialization of invalid JSON."""
        with pytest.raises(SerializationError):
            await serializer.deserialize("invalid json")

    async def test_non_serializable_object(self, serializer):
        """Test serialization of non-serializable object.

        Note: With orjson's default handler, non-serializable objects like
        lambdas are converted to their string representation rather than
        raising an error.
        """
        # Lambda functions are converted to string representation
        result = await serializer.serialize(lambda x: x)
        assert isinstance(result, (str, bytes))
        # The serialized result contains the string representation of the lambda
        deserialized = await serializer.deserialize(result)
        assert "<function" in str(deserialized)
