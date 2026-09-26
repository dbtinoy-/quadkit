"""Tests for cache service decorators module"""

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.config import CacheOperationConfig
from quadkit.cache.serialization.type_registry import DEFAULT_REGISTRY
from quadkit.cache.service.decorators import (
    CacheDecorator,
    cache,
    conditional_cache,
    invalidate_cache,
    remember,
)
from quadkit.domain import DomainModel
from quadkit.result import Ok


@dataclass
class _User(DomainModel):
    """Domain model used as the registered cached type."""

    user_id: str
    name: str


class _Hostile:
    """Module-level class whose envelope must never be imported on read."""


class TestCacheDecorator:
    """Test the @cache decorator"""

    @pytest.fixture
    def mock_service(self):
        """Create a mock CacheService"""
        service = MagicMock()
        service.get_or_set = AsyncMock()
        return service

    @pytest.fixture
    def mock_service_get_set(self):
        """Create a mock CacheService with separate get/set methods"""
        service = MagicMock()
        service.get = AsyncMock(return_value=None)
        service.set = AsyncMock()
        service.delete = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_cache_decorator_calls_service(self, mock_service):
        """Test that @cache decorator calls the service correctly"""

        @cache(mock_service, key_prefix="test", ttl=300)
        async def test_function(x, y=10):
            return x + y

        mock_service.get_or_set.return_value = 42

        result = await test_function(5, y=15)

        assert result == 42
        mock_service.get_or_set.assert_called_once()
        call_args = mock_service.get_or_set.call_args
        assert call_args[0][0].startswith("test:")  # cache key
        # The lambda function should return the result when awaited
        lambda_result = await call_args[0][1]()
        assert lambda_result == 20  # function result
        assert call_args[0][2] == 300  # ttl
        assert call_args[0][3] is None  # backend
        assert call_args[0][4] is True  # protect

    @pytest.mark.asyncio
    async def test_cache_decorator_key_generation(self, mock_service):
        """Test that @cache decorator generates consistent keys"""

        @cache(mock_service, key_prefix="api")
        async def api_call(user_id, action="get"):
            return f"{user_id}-{action}"

        # Call twice with same args
        await api_call(123, action="update")
        await api_call(123, action="update")

        # Should generate same key both times
        assert mock_service.get_or_set.call_count == 2
        key1 = mock_service.get_or_set.call_args_list[0][0][0]
        key2 = mock_service.get_or_set.call_args_list[1][0][0]
        assert key1 == key2
        assert "api:" in key1
        assert "api_call" in key1

    @pytest.mark.asyncio
    async def test_remember_decorator(self, mock_service):
        """Test that @remember decorator works"""

        @remember(mock_service, ttl=600)
        async def expensive_calc(x, y):
            return x * y + 42

        mock_service.get_or_set.return_value = 100

        result = await expensive_calc(5, 10)

        assert result == 100
        mock_service.get_or_set.assert_called_once()
        call_args = mock_service.get_or_set.call_args
        assert call_args[0][0].startswith("remember:")
        # The lambda function should return the result when awaited
        lambda_result = await call_args[0][1]()
        assert lambda_result == 92  # 5 * 10 + 42
        assert call_args[0][2] == 600

    @pytest.mark.asyncio
    async def test_conditional_cache_decorator_condition_met(
        self, mock_service_get_set,
    ):
        """Test conditional caching when condition is met"""

        @conditional_cache(
            mock_service_get_set, lambda result: result > 10, key_prefix="big", ttl=300,
        )
        async def maybe_big_number(x):
            return x * 2

        # First call - not cached
        result1 = await maybe_big_number(6)  # 12 > 10, should cache
        assert result1 == 12
        mock_service_get_set.get.assert_called_once()
        mock_service_get_set.set.assert_called_once()

        # Reset mocks
        mock_service_get_set.get.reset_mock()
        mock_service_get_set.set.reset_mock()
        mock_service_get_set.get.return_value = 12

        # Second call - should get from cache
        result2 = await maybe_big_number(6)
        assert result2 == 12
        mock_service_get_set.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_conditional_cache_decorator_condition_not_met(
        self, mock_service_get_set,
    ):
        """Test conditional caching when condition is not met"""

        @conditional_cache(mock_service_get_set, lambda result: result > 10, ttl=300)
        async def maybe_big_number(x):
            return x * 2

        # Call with small number - should not cache
        result = await maybe_big_number(3)  # 6 <= 10, should not cache
        assert result == 6
        mock_service_get_set.get.assert_called_once()
        mock_service_get_set.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_invalidate_cache_decorator(self, mock_service_get_set):
        """Test that @invalidate_cache decorator invalidates after execution"""

        @invalidate_cache(mock_service_get_set, "user:123:*")
        async def update_user(user_id, data):
            return {"id": user_id, "updated": True}

        result = await update_user(123, {"name": "John"})

        assert result == {"id": 123, "updated": True}
        mock_service_get_set.delete.assert_called_once_with("user:123:*", None)

    @pytest.mark.asyncio
    async def test_invalidate_cache_decorator_with_backend(self, mock_service_get_set):
        """Test invalidate cache with specific backend"""

        @invalidate_cache(mock_service_get_set, "session:*", backend="redis")
        async def logout(session_id):
            return True

        await logout("abc123")

        mock_service_get_set.delete.assert_called_once_with("session:*", "redis")

    @pytest.mark.asyncio
    async def test_invalidate_cache_decorator_handles_errors(
        self, mock_service_get_set,
    ):
        """Test that invalidate cache handles deletion errors gracefully"""

        @invalidate_cache(mock_service_get_set, "key:*")
        async def some_function():
            return "done"

        mock_service_get_set.delete.side_effect = RuntimeError("Cache error")

        # Should not raise exception
        result = await some_function()
        assert result == "done"
        mock_service_get_set.delete.assert_called_once()


class TestCacheDecoratorClass:
    """Test the CacheDecorator class"""

    @pytest.fixture
    def mock_service(self):
        """Create a mock CacheService"""
        service = MagicMock()
        service.get_or_set = AsyncMock()
        return service

    def test_cache_decorator_class_remember_strategy(self, mock_service):
        """Test CacheDecorator class with remember strategy"""

        decorator = CacheDecorator(mock_service, strategy="remember", ttl=600)

        @decorator
        async def test_func(x):
            return x * 2

        assert hasattr(test_func, "__wrapped__")  # Should be wrapped

    def test_cache_decorator_class_cache_strategy(self, mock_service):
        """Test CacheDecorator class with cache strategy"""

        decorator = CacheDecorator(
            mock_service,
            strategy="cache",
            key_prefix="api",
            ttl=300,
            backend="redis",
            protect=False,
        )

        @decorator
        async def api_func(x):
            return x + 1

        assert hasattr(api_func, "__wrapped__")

    def test_cache_decorator_class_conditional_strategy(self, mock_service):
        """Test CacheDecorator class with conditional strategy"""

        decorator = CacheDecorator(
            mock_service,
            strategy="conditional",
            condition=lambda r: r is not None,
            key_prefix="optional",
        )

        @decorator
        async def optional_func(x):
            return x if x > 0 else None

        assert hasattr(optional_func, "__wrapped__")

    def test_cache_decorator_class_invalid_strategy(self, mock_service):
        """Test CacheDecorator class with invalid strategy"""

        decorator = CacheDecorator(mock_service, strategy="invalid")

        with pytest.raises(ValueError, match="Unknown caching strategy"):
            decorator(lambda: None)

    def test_cache_decorator_class_conditional_without_condition(self, mock_service):
        """Test CacheDecorator conditional strategy without condition function"""

        decorator = CacheDecorator(mock_service, strategy="conditional")

        with pytest.raises(ValueError, match="condition_func is required"):
            decorator(lambda: None)


class TestDecoratorIntegration:
    """Integration tests for decorators working together"""

    @pytest.fixture
    def mock_service(self):
        """Create a mock CacheService"""
        service = MagicMock()
        service.get_or_set = AsyncMock(return_value="cached_result")
        service.get = AsyncMock(return_value=None)
        service.set = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_multiple_decorators_on_same_function(self, mock_service):
        """Test that multiple decorators can be applied (though not recommended)"""

        # Apply both cache and remember decorators
        @cache(mock_service, key_prefix="outer")
        @remember(mock_service, ttl=300)
        async def complex_func(x):
            return f"result_{x}"

        result = await complex_func(42)

        # The outer decorator (@cache) should control the behavior
        assert result == "cached_result"
        # Should call the cache decorator's service method
        mock_service.get_or_set.assert_called_once()

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self, mock_service):
        """Test that decorators preserve function metadata"""

        @cache(mock_service)
        async def documented_func(x: int, y: str = "default") -> str:
            """A well-documented function."""
            return f"{x}_{y}"

        assert documented_func.__name__ == "documented_func"
        assert documented_func.__doc__ == "A well-documented function."
        assert documented_func.__annotations__ == {"x": int, "y": str, "return": str}


class TestCacheableTypedLookup:
    """@cacheable envelope reconstruction via the registered type registry."""

    @pytest.fixture
    def backend(self) -> MemoryCacheBackend:
        """In-memory cache backend with a real store."""
        config = CacheOperationConfig(default_ttl=300, key_prefix="test")
        backend = MemoryCacheBackend(config)
        backend._store.get = AsyncMock(side_effect=backend._store.get)
        backend._store.set = AsyncMock(side_effect=backend._store.set)
        return backend

    @pytest.fixture
    def registered_user(self) -> type[_User]:
        """Register _User on DEFAULT_REGISTRY for the duration of a test."""
        DEFAULT_REGISTRY.register(_User)
        yield _User
        DEFAULT_REGISTRY.clear()

    def test_deserialize_unknown_tag_returns_raw_payload_without_import(self) -> None:
        """A hostile envelope naming os.system is never imported (D3 poisoning)."""
        from quadkit.cache.decorators import _deserialize

        poisoned = {
            "__lx_module__": "os",
            "__lx_class__": "system",
            "__lx_data__": {"cmd": "echo boom"},
        }
        result = _deserialize(poisoned)
        assert result == {"cmd": "echo boom"}

    def test_deserialize_unregistered_local_class_degrades_to_data(self) -> None:
        """A real-but-unregistered class envelope degrades to raw data."""
        from quadkit.cache.decorators import _deserialize

        payload = {
            "__lx_module__": _Hostile.__module__,
            "__lx_class__": _Hostile.__qualname__,
            "__lx_data__": {"marker": True},
        }
        result = _deserialize(payload)
        assert result == {"marker": True}

    @pytest.mark.asyncio
    async def test_registered_type_round_trip(
        self, backend: MemoryCacheBackend, registered_user: type[_User],
    ) -> None:
        """A registered domain model survives the cache round-trip."""
        from quadkit.cache.decorators import cacheable

        class Service:
            def __init__(self) -> None:
                self._cache = backend

            @cacheable(ttl=60, key_prefix="users")
            async def get_user(self, user_id: str) -> _User:
                return _User(user_id=user_id, name="Ada")

        service = Service()
        result = await service.get_user("u1")

        assert isinstance(result, _User)
        assert result.user_id == "u1"
        assert result.name == "Ada"

        cached = await service.get_user("u1")
        assert isinstance(cached, _User)
        assert cached.user_id == "u1"
        assert cached.name == "Ada"

    @pytest.mark.asyncio
    async def test_result_wrapped_registered_type(
        self, backend: MemoryCacheBackend, registered_user: type[_User],
    ) -> None:
        """A Result-wrapped registered domain model round-trips as Ok."""
        from quadkit.cache.decorators import cacheable

        class Service:
            def __init__(self) -> None:
                self._cache = backend

            @cacheable(ttl=60, key_prefix="users")
            async def get_user(self, user_id: str):
                return Ok(_User(user_id=user_id, name="Grace"))

        service = Service()
        first = await service.get_user("u2")
        assert first.is_ok()

        second = await service.get_user("u2")
        assert second.is_ok()
        cached_user = second.unwrap()
        assert isinstance(cached_user, _User)
        assert cached_user.name == "Grace"

    @pytest.mark.asyncio
    async def test_unregistered_type_denied_by_default(
        self, backend: MemoryCacheBackend,
    ) -> None:
        """An unregistered type envelope is never reconstructed."""
        from quadkit.cache.decorators import cacheable

        class Service:
            def __init__(self) -> None:
                self._cache = backend

            @cacheable(ttl=60, key_prefix="secrets")
            async def get_secret(self, secret: str) -> _User:
                return _User(user_id="u3", name=secret)

        service = Service()
        first = await service.get_secret("hunter2")
        assert isinstance(first, _User)

        # Second call reads the cached envelope; since the type is not
        # registered it must degrade to raw data, never be reconstructed.
        second = await service.get_secret("hunter2")
        assert isinstance(second, dict)
        assert second.get("name") == "hunter2"
