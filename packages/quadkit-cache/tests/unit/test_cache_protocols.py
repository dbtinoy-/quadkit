"""Unit tests for quadkit-cache protocols.

These tests verify the protocols defined in quadkit.cache.protocols.
"""

from typing import Any

from quadkit.cache.protocols import (
    CacheBackendProtocol,
    CacheHealthCheckProtocol,
    CacheKeyBuilderProtocol,
    CacheProtectionStrategyProtocol,
    CacheProviderProtocol,
    CacheSerializerProtocol,
)


class TestCacheProviderProtocol:
    """Tests for CacheProviderProtocol."""

    def test_cache_provider_protocol_exists(self) -> None:
        assert CacheProviderProtocol is not None

    def test_cache_provider_protocol_is_protocol(self) -> None:
        # Protocols should have __protocol_attrs__
        assert hasattr(CacheProviderProtocol, "__protocol_attrs__") or hasattr(CacheProviderProtocol, "__annotations__")

    def test_cache_provider_protocol_get_backend_method(self) -> None:
        # Check that the protocol defines get_backend method
        assert "get_backend" in dir(CacheProviderProtocol)


class TestCacheHealthCheckProtocol:
    """Tests for CacheHealthCheckProtocol."""

    def test_cache_health_check_protocol_exists(self) -> None:
        assert CacheHealthCheckProtocol is not None

    def test_cache_health_check_protocol_is_protocol(self) -> None:
        assert hasattr(CacheHealthCheckProtocol, "__protocol_attrs__") or hasattr(CacheHealthCheckProtocol, "__annotations__")

    def test_cache_health_check_protocol_check_health_method(self) -> None:
        # Check that the protocol defines check_health method
        assert "check_health" in dir(CacheHealthCheckProtocol)


class TestCacheKeyBuilderProtocol:
    """Tests for CacheKeyBuilderProtocol."""

    def test_cache_key_builder_protocol_exists(self) -> None:
        assert CacheKeyBuilderProtocol is not None

    def test_cache_key_builder_protocol_is_protocol(self) -> None:
        assert hasattr(CacheKeyBuilderProtocol, "__protocol_attrs__") or hasattr(CacheKeyBuilderProtocol, "__annotations__")

    def test_cache_key_builder_protocol_build_key_method(self) -> None:
        # Check that the protocol defines build_key method
        assert "build_key" in dir(CacheKeyBuilderProtocol)


class TestCacheProtectionStrategyProtocol:
    """Tests for CacheProtectionStrategyProtocol."""

    def test_cache_protection_strategy_protocol_exists(self) -> None:
        assert CacheProtectionStrategyProtocol is not None

    def test_cache_protection_strategy_protocol_is_protocol(self) -> None:
        assert hasattr(CacheProtectionStrategyProtocol, "__protocol_attrs__") or hasattr(CacheProtectionStrategyProtocol, "__annotations__")

    def test_cache_protection_strategy_protocol_should_protect_method(self) -> None:
        # Check that the protocol defines should_protect method
        assert "should_protect" in dir(CacheProtectionStrategyProtocol)


class TestCacheSerializerProtocol:
    """Tests for CacheSerializerProtocol."""

    def test_cache_serializer_protocol_exists(self) -> None:
        assert CacheSerializerProtocol is not None

    def test_cache_serializer_protocol_is_protocol(self) -> None:
        assert hasattr(CacheSerializerProtocol, "__protocol_attrs__") or hasattr(CacheSerializerProtocol, "__annotations__")

    def test_cache_serializer_protocol_serialize_method(self) -> None:
        assert "serialize" in dir(CacheSerializerProtocol)

    def test_cache_serializer_protocol_deserialize_method(self) -> None:
        assert "deserialize" in dir(CacheSerializerProtocol)


class TestCacheBackendProtocol:
    """Tests for CacheBackendProtocol (re-exported from contracts)."""

    def test_cache_backend_protocol_exists(self) -> None:
        assert CacheBackendProtocol is not None

    def test_cache_backend_protocol_is_protocol(self) -> None:
        assert hasattr(CacheBackendProtocol, "__protocol_attrs__") or hasattr(CacheBackendProtocol, "__annotations__")


class TestProtocolRuntimeCheckable:
    """Tests for runtime_checkable decorator."""

    def test_cache_provider_protocol_is_runtime_checkable(self) -> None:
        assert getattr(CacheProviderProtocol, "_is_protocol", False) is not False

    def test_cache_health_check_protocol_is_runtime_checkable(self) -> None:
        assert getattr(CacheHealthCheckProtocol, "_is_protocol", False) is not False


class TestMockImplementation:
    """Tests using mock implementations of protocols."""

    def test_mock_provider_implements_protocol(self) -> None:
        """A mock object can satisfy the protocol if it has the required methods."""

        class MockProvider:
            def get_backend(self, name: str | None = None) -> Any:
                return None

        mock = MockProvider()
        # Should be runtime checkable
        assert isinstance(mock, CacheProviderProtocol)

    def test_mock_health_checker_implements_protocol(self) -> None:
        """A mock health checker can satisfy the protocol."""

        class MockHealthChecker:
            async def check_health(self) -> dict[str, Any]:
                return {"status": "healthy"}

        mock = MockHealthChecker()
        assert isinstance(mock, CacheHealthCheckProtocol)

    def test_mock_key_builder_implements_protocol(self) -> None:
        """A mock key builder can satisfy the protocol."""

        class MockKeyBuilder:
            def build_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
                return f"{prefix}:{args}:{kwargs}"

        mock = MockKeyBuilder()
        assert isinstance(mock, CacheKeyBuilderProtocol)

    def test_mock_protection_strategy_implements_protocol(self) -> None:
        """A mock protection strategy can satisfy the protocol."""

        class MockProtectionStrategy:
            async def should_protect(self, key: str) -> bool:
                return True

        mock = MockProtectionStrategy()
        assert isinstance(mock, CacheProtectionStrategyProtocol)

    def test_mock_serializer_implements_protocol(self) -> None:
        """A mock serializer can satisfy the protocol."""

        class MockSerializer:
            def serialize(self, value: Any) -> bytes | str:
                return str(value).encode()

            def deserialize(self, data: bytes | str) -> Any:
                if isinstance(data, bytes):
                    data = data.decode()
                return data

        mock = MockSerializer()
        assert isinstance(mock, CacheSerializerProtocol)


class TestProtocolAllExports:
    """Tests to verify __all__ exports."""

    def test_all_contains_expected_protocols(self) -> None:
        from quadkit.cache import protocols as proto_module

        expected = [
            "CacheBackendProtocol",
            "CacheHealthCheckProtocol",
            "CacheKeyBuilderProtocol",
            "CacheProtectionStrategyProtocol",
            "CacheProviderProtocol",
            "CacheSerializerProtocol",
        ]
        for item in expected:
            assert item in proto_module.__all__
