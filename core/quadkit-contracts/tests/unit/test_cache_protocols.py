"""Tests for cache protocol definitions."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.infra.cache.protocols import (
    CacheBackendProtocol,
    CacheHealthCheckerProtocol,
    CacheKeyBuilderProtocol,
    CacheProtectionStrategyProtocol,
    CacheProviderProtocol,
)


class TestCacheBackendProtocol:
    """Tests for CacheBackendProtocol."""

    @pytest.mark.asyncio
    async def test_has_get_method(self) -> None:
        """Test protocol has get async method."""

        from quadkit.contracts.core.result import Ok

        class Backend:
            async def get(self, key: str) -> Any:
                return Ok("value")

        backend = Backend()
        result = await backend.get("key1")
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_has_set_method(self) -> None:
        """Test protocol has set async method."""

        from quadkit.contracts.core.result import Ok

        class Backend:
            async def set(
                self, key: str, value: Any, ttl: int | None = None
            ) -> Any:
                return Ok(None)

        backend = Backend()
        result = await backend.set("key1", "value")
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_has_delete_method(self) -> None:
        """Test protocol has delete async method."""

        from quadkit.contracts.core.result import Ok

        class Backend:
            async def delete(self, key: str) -> Any:
                return Ok(True)

        backend = Backend()
        result = await backend.delete("key1")
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_has_delete_many_method(self) -> None:
        """Test protocol has delete_many async method."""

        from quadkit.contracts.core.result import Ok

        class Backend:
            async def delete_many(self, keys: list[str]) -> Any:
                return Ok(1)

        backend = Backend()
        result = await backend.delete_many(["key1", "key2"])
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_has_delete_pattern_method(self) -> None:
        """Test protocol has delete_pattern async method."""

        from quadkit.contracts.core.result import Ok

        class Backend:
            async def delete_pattern(self, pattern: str) -> Any:
                return Ok(1)

        backend = Backend()
        result = await backend.delete_pattern("key:*")
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_has_exists_method(self) -> None:
        """Test protocol has exists async method."""

        from quadkit.contracts.core.result import Ok

        class Backend:
            async def exists(self, key: str) -> Any:
                return Ok(True)

        backend = Backend()
        result = await backend.exists("key1")
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_has_clear_method(self) -> None:
        """Test protocol has clear async method."""

        from quadkit.contracts.core.result import Ok

        class Backend:
            async def clear(self) -> Any:
                return Ok(None)

        backend = Backend()
        result = await backend.clear()
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_has_get_many_method(self) -> None:
        """Test protocol has get_many async method."""

        from quadkit.contracts.core.result import Ok

        class Backend:
            async def get_many(self, keys: list[str]) -> Any:
                return Ok({})

        backend = Backend()
        result = await backend.get_many(["key1", "key2"])
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_has_set_many_method(self) -> None:
        """Test protocol has set_many async method."""

        from quadkit.contracts.core.result import Ok

        class Backend:
            async def set_many(
                self, items: dict[str, Any], ttl: int | None = None
            ) -> Any:
                return Ok(None)

        backend = Backend()
        result = await backend.set_many({"key1": "value"})
        assert result.is_ok()

    @pytest.mark.asyncio
    async def test_has_health_check_method(self) -> None:
        """Test protocol has health_check async method."""

        class Backend:
            async def health_check(self, timeout: float = 5.0) -> Any:
                return {"status": "healthy"}

        backend = Backend()
        result = await backend.health_check()
        assert result["status"] == "healthy"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        from quadkit.contracts.core.result import Ok

        class Backend:
            async def get(self, key: str) -> Any:
                return Ok(None)

            async def set(self, key: str, value: Any, **kwargs: Any) -> Any:
                return Ok(None)

            async def delete(self, key: str) -> Any:
                return Ok(False)

            async def delete_many(self, keys: list[str]) -> Any:
                return Ok(0)

            async def delete_pattern(self, pattern: str) -> Any:
                return Ok(0)

            async def exists(self, key: str) -> Any:
                return Ok(False)

            async def clear(self) -> Any:
                return Ok(None)

            async def get_many(self, keys: list[str]) -> Any:
                return Ok({})

            async def set_many(self, items: dict, **kwargs: Any) -> Any:
                return Ok(None)

            async def health_check(self, timeout: float = 5.0) -> Any:
                return {}

        assert isinstance(Backend(), CacheBackendProtocol)


class TestCacheProtectionStrategyProtocol:
    """Tests for CacheProtectionStrategyProtocol."""

    @pytest.mark.asyncio
    async def test_has_acquire_lock_method(self) -> None:
        """Test protocol has acquire_lock async method."""

        class Strategy:
            async def acquire_lock(self, key: str, ttl: int) -> bool:
                return True

        strategy = Strategy()
        result = await strategy.acquire_lock("key1", 10)
        assert result is True

    @pytest.mark.asyncio
    async def test_has_release_lock_method(self) -> None:
        """Test protocol has release_lock async method."""

        class Strategy:
            async def release_lock(self, key: str) -> bool:
                return True

        strategy = Strategy()
        result = await strategy.release_lock("key1")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_wait_for_value_method(self) -> None:
        """Test protocol has wait_for_value async method."""

        class Strategy:
            async def wait_for_value(
                self,
                key: str,
                timeout: float,
                check_interval: float = 0.1,
            ) -> Any | None:
                return "value"

        strategy = Strategy()
        result = await strategy.wait_for_value("key1", 1.0)
        assert result is not None

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Strategy:
            async def acquire_lock(self, key: str, ttl: int) -> bool:
                return False

            async def release_lock(self, key: str) -> bool:
                return False

            async def wait_for_value(self, key: str, timeout: float, **kwargs: Any) -> Any | None:
                return None

        assert isinstance(Strategy(), CacheProtectionStrategyProtocol)


class TestCacheKeyBuilderProtocol:
    """Tests for CacheKeyBuilderProtocol."""

    def test_has_build_key_method(self) -> None:
        """Test protocol has build_key method."""

        class Builder:
            def build_key(
                self,
                func: Any,
                args: tuple[Any, ...],
                kwargs: dict[str, Any],
                prefix: str | None = None,
            ) -> str:
                return f"{func.__name__}:{args}"

        builder = Builder()
        result = builder.build_key(lambda: None, (), {})
        assert isinstance(result, str)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Builder:
            def build_key(
                self,
                func: Any,
                args: tuple,
                kwargs: dict,
                prefix: str | None = None,
            ) -> str:
                return ""

        assert isinstance(Builder(), CacheKeyBuilderProtocol)


class TestCacheHealthCheckerProtocol:
    """Tests for CacheHealthCheckerProtocol."""

    @pytest.mark.asyncio
    async def test_has_health_check_method(self) -> None:
        """Test protocol has health_check async method."""

        class Checker:
            async def health_check(self, timeout: float = 5.0) -> Any:
                return {"status": "healthy"}

        checker = Checker()
        result = await checker.health_check()
        assert result["status"] == "healthy"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Checker:
            async def health_check(self, timeout: float = 5.0) -> Any:
                return {}

        assert isinstance(Checker(), CacheHealthCheckerProtocol)


class TestCacheProviderProtocol:
    """Tests for CacheProviderProtocol."""

    def test_protocol_has_provider_methods(self) -> None:
        """Test CacheProviderProtocol has Provider methods."""


        assert hasattr(CacheProviderProtocol, "name")
        assert hasattr(CacheProviderProtocol, "priority")
        assert hasattr(CacheProviderProtocol, "register")
        assert hasattr(CacheProviderProtocol, "boot")

    def test_protocol_extends_provider(self) -> None:
        """Test protocol extends ProviderProtocol."""
        assert hasattr(CacheProviderProtocol, "name")
        assert hasattr(CacheProviderProtocol, "priority")
        assert hasattr(CacheProviderProtocol, "register")
