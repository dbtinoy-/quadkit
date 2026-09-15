"""Test protocol validation utilities."""

from typing import Protocol, runtime_checkable

import pytest

from quadkit.di.extensions.validator import validate_protocol


@runtime_checkable
class CacheProtocol(Protocol):
    """Test protocol for cache implementations."""

    async def get(self, key: str) -> str | None: ...

    async def set(self, key: str, value: str) -> None: ...

    async def delete(self, key: str) -> None: ...


class ValidCache:
    """Valid cache implementation."""

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str) -> None:
        pass

    async def delete(self, key: str) -> None:
        pass


class InvalidCache:
    """Invalid cache implementation - missing delete method."""

    async def get(self, key: str) -> str | None:
        return None

    async def set(self, key: str, value: str) -> None:
        pass


class TestProtocolValidation:
    """Test protocol validation functionality."""

    def test_valid_implementation_passes(self):
        """Test that functionality valid implementations pass validation."""
        cache = ValidCache()
        validate_protocol(cache, CacheProtocol)

    def test_missing_method_fails(self):
        """Test that missing methods cause validation to fail."""
        cache = InvalidCache()

        with pytest.raises(TypeError) as exc_info:
            validate_protocol(cache, CacheProtocol)

        assert "missing member 'delete'" in str(exc_info.value)
