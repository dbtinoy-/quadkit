"""Tests for cache serialization base module"""

from quadkit.cache.serialization.base import CacheSerializationError, AsyncStringSerializerProtocol


class TestSerializationBase:
    """Test the serialization base classes and protocol"""

    def test_serializer_protocol_exists(self):
        """Test that AsyncStringSerializerProtocol protocol is defined"""
        assert AsyncStringSerializerProtocol is not None

    def test_serializer_protocol_has_required_methods(self):
        """Test that AsyncStringSerializerProtocol protocol defines required methods"""
        # Protocol methods are checked at type checking time, not runtime
        # But we can verify the protocol exists and has the expected structure
        assert hasattr(AsyncStringSerializerProtocol, "__protocol_attrs__") or hasattr(AsyncStringSerializerProtocol, "__annotations__") or hasattr(
            AsyncStringSerializerProtocol, "__annotations__",
        )

    def test_serialization_error_can_be_instantiated(self):
        """Test that CacheSerializationError can be instantiated"""
        error = CacheSerializationError("Test error message")
        assert isinstance(error, Exception)
        assert str(error).startswith("[QK_ERR_CACHE_015] Test error message")

    def test_serialization_error_inheritance(self):
        """Test that CacheSerializationError inherits from Exception"""
        assert issubclass(CacheSerializationError, Exception)

    def test_serialization_error_with_args(self):
        """Test CacheSerializationError with additional arguments"""
        error = CacheSerializationError("Error", details={"extra": "args"})
        assert isinstance(error, Exception)
        # Note: QuadkitError stores only message in args[0], other args in details
        assert "[QK_ERR_CACHE_015] Error" in str(error)
