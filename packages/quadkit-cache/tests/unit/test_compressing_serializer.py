"""Tests for CompressingSerializer."""

import pickle
from unittest.mock import patch

import pytest

from quadkit.cache.exceptions import CacheSerializationError as SerializationError
from quadkit.cache.serialization.compression import CompressingSerializer


class _HostilePickleTarget:
    """Module-level hostile class for RCE-gadget tests."""

    def __reduce__(self):
        import os

        return (os.system, ("echo pwned",))


class _BenignCustomType:
    """Module-level custom class whose pickled global reference must be denied."""


class _Gadget:
    """Module-level class with an attribute for allowlist round-trip tests."""

    def __init__(self) -> None:
        self.payload = "boom"


class TestCompressingSerializer:
    """Test CompressingSerializer functionality."""

    def test_init_defaults(self):
        """Test default initialization."""
        serializer = CompressingSerializer()
        assert serializer._threshold == 1024
        assert serializer._level == 6

    def test_init_custom(self):
        """Test custom initialization."""
        serializer = CompressingSerializer(
            compression_threshold=2048,
            compression_level=9,
        )
        assert serializer._threshold == 2048
        assert serializer._level == 9

    @pytest.mark.asyncio
    async def test_serialize_small_value_no_compression(self):
        """Test small values are not compressed."""
        serializer = CompressingSerializer(compression_threshold=1000)
        value = "small string"

        result = await serializer.serialize(value)

        # Should be hex-encoded bytes with uncompressed marker
        data = bytes.fromhex(result)
        assert data[0] == CompressingSerializer.MARKER_UNCOMPRESSED[0]

        # Should be able to deserialize back
        deserialized = await serializer.deserialize(result)
        assert deserialized == value

    @pytest.mark.asyncio
    async def test_serialize_large_value_compression(self):
        """Test large values are compressed."""
        serializer = CompressingSerializer(compression_threshold=100)
        value = "x" * 1000  # Large string

        result = await serializer.serialize(value)

        # Should be hex-encoded bytes with compressed marker
        data = bytes.fromhex(result)
        assert data[0] == CompressingSerializer.MARKER_COMPRESSED[0]

        # Should be able to deserialize back
        deserialized = await serializer.deserialize(result)
        assert deserialized == value

    @pytest.mark.asyncio
    async def test_serialize_compression_ineffective(self):
        """Test compression is skipped if it doesn't help."""
        serializer = CompressingSerializer(compression_threshold=10)

        # Mock zlib.compress to return larger data (simulating ineffective compression)
        # Since we use asyncio.to_thread, we need to be careful with patching sync zlib.compress
        with patch("zlib.compress") as mock_compress:
            value = "x" * 100
            # Return compressed data that's larger than original
            mock_compress.return_value = b"larger_than_original" * 10

            result = await serializer.serialize(value)

            # Should use uncompressed marker even though over threshold
            data = bytes.fromhex(result)
            assert data[0] == CompressingSerializer.MARKER_UNCOMPRESSED[0]

            # Should still deserialize correctly
            deserialized = await serializer.deserialize(result)
            assert deserialized == value

    @pytest.mark.asyncio
    async def test_serialize_complex_objects(self):
        """Test serialization of complex objects."""
        serializer = CompressingSerializer()
        value = {
            "list": [1, 2, {"nested": "dict"}],
            "tuple": (1, 2, 3),
            "set": {1, 2, 3},
        }

        result = await serializer.serialize(value)
        deserialized = await serializer.deserialize(result)
        assert deserialized == value

    @pytest.mark.asyncio
    async def test_deserialize_invalid_marker(self):
        """Test deserialization with invalid marker."""
        serializer = CompressingSerializer()

        # Create invalid data with bad marker
        invalid_data = b"\x99" + pickle.dumps("test")
        invalid_hex = invalid_data.hex()

        with pytest.raises(SerializationError, match="Invalid compression marker"):
            await serializer.deserialize(invalid_hex)

    @pytest.mark.asyncio
    async def test_deserialize_empty_data(self):
        """Test deserialization of empty data."""
        serializer = CompressingSerializer()

        with pytest.raises(SerializationError, match="Empty data"):
            await serializer.deserialize("")

    @pytest.mark.asyncio
    async def test_deserialize_invalid_hex(self):
        """Test deserialization with invalid hex."""
        serializer = CompressingSerializer()

        with pytest.raises(SerializationError):
            await serializer.deserialize("invalid_hex")

    @pytest.mark.asyncio
    async def test_deserialize_corrupted_compressed_data(self):
        """Test deserialization of corrupted compressed data."""
        serializer = CompressingSerializer()

        # Create corrupted compressed data
        corrupted = (CompressingSerializer.MARKER_COMPRESSED + b"corrupted").hex()

        with pytest.raises(SerializationError):
            await serializer.deserialize(corrupted)

    @pytest.mark.asyncio
    async def test_deserialize_corrupted_uncompressed_data(self):
        """Test deserialization of corrupted uncompressed data."""
        serializer = CompressingSerializer()

        # Create corrupted uncompressed data
        corrupted = (CompressingSerializer.MARKER_UNCOMPRESSED + b"corrupted").hex()

        with pytest.raises(SerializationError):
            await serializer.deserialize(corrupted)

    @pytest.mark.asyncio
    async def test_serialize_unpicklable_object(self):
        """Test serialization of unpicklable object."""
        serializer = CompressingSerializer()

        # Mock pickle to raise error
        with patch("pickle.dumps", side_effect=pickle.PicklingError("Can't pickle")):
            with pytest.raises(SerializationError, match="Failed to serialize value"):
                await serializer.serialize(lambda x: x)

    @pytest.mark.asyncio
    async def test_deserialize_unpicklable_data(self):
        """Test deserialization of corrupted pickle data."""
        serializer = CompressingSerializer()

        # Create data with corrupted pickle
        corrupted = (CompressingSerializer.MARKER_UNCOMPRESSED + b"corrupted").hex()

        with pytest.raises(SerializationError, match="Failed to deserialize value"):
            await serializer.deserialize(corrupted)

    @pytest.mark.asyncio
    async def test_deserialize_rejects_unsafe_global(self):
        """Test deserialization rejects payloads referencing non-builtin globals."""
        serializer = CompressingSerializer()

        hostile = (
            serializer.MARKER_UNCOMPRESSED + pickle.dumps(_BenignCustomType())
        ).hex()

        with pytest.raises(SerializationError):
            await serializer.deserialize(hostile)

    @pytest.mark.asyncio
    async def test_deserialize_rejects_os_system_gadget(self):
        """Test deserialization rejects the classic os.system gadget."""
        serializer = CompressingSerializer()

        payload = (
            serializer.MARKER_UNCOMPRESSED + pickle.dumps(_HostilePickleTarget())
        ).hex()

        with pytest.raises(SerializationError):
            await serializer.deserialize(payload)

    @pytest.mark.asyncio
    async def test_deserialize_denies_unallowed_class(self):
        """Test empty allowlist denies every custom class (deny-by-default)."""
        serializer = CompressingSerializer(allowed_classes=())

        hostile = (
            serializer.MARKER_UNCOMPRESSED + pickle.dumps(_Gadget())
        ).hex()

        with pytest.raises(SerializationError):
            await serializer.deserialize(hostile)

    @pytest.mark.asyncio
    async def test_deserialize_allows_configured_class(self):
        """Test an explicitly allowlisted class round-trips."""
        serializer = CompressingSerializer(allowed_classes=(_Gadget,))

        value = (serializer.MARKER_UNCOMPRESSED + pickle.dumps(_Gadget())).hex()
        result = await serializer.deserialize(value)

        assert isinstance(result, _Gadget)
        assert result.payload == "boom"

    @pytest.mark.asyncio
    async def test_roundtrip_various_types(self):
        """Test roundtrip serialization for various types."""
        serializer = CompressingSerializer()

        test_values = [
            None,
            42,
            3.14,
            "string",
            b"bytes",
            [1, 2, 3],
            {"key": "value"},
            (1, 2, 3),
            {1, 2, 3},
            True,
            False,
        ]

        for value in test_values:
            result = await serializer.serialize(value)
            deserialized = await serializer.deserialize(result)
            assert deserialized == value, f"Failed for {type(value).__name__}: {value}"

    def test_get_stats(self):
        """Test get_stats method."""
        serializer = CompressingSerializer(
            compression_threshold=2048,
            compression_level=9,
        )

        stats = serializer.get_stats()
        assert stats == {
            "compression_threshold": 2048,
            "compression_level": 9,
        }

    @pytest.mark.asyncio
    async def test_compression_ratio_logging(self):
        """Test compression ratio is logged."""
        serializer = CompressingSerializer(compression_threshold=10)

        with patch("quadkit.cache.serialization.compression.logger") as mock_logger:
            large_value = "x" * 1000
            await serializer.serialize(large_value)

            # Should log compression info
            mock_logger.debug.assert_called()
            call_args = mock_logger.debug.call_args[0][0]
            assert "Compressed:" in call_args
            assert "bytes" in call_args

    @pytest.mark.asyncio
    async def test_compression_ineffective_logging(self):
        """Test ineffective compression is logged."""
        serializer = CompressingSerializer(compression_threshold=10)

        with patch("quadkit.cache.serialization.compression.logger") as mock_logger:
            # Mock zlib.compress to return larger data (ineffective compression)
            with patch("zlib.compress") as mock_compress:
                large_value = "x" * 100
                # Return compressed data that's larger than original
                mock_compress.return_value = b"larger" * 100  # Much larger

                await serializer.serialize(large_value)

                # Should log ineffective compression
                mock_logger.debug.assert_called()
                call_args = mock_logger.debug.call_args[0][0]
                assert "Compression ineffective:" in call_args
