"""Round 33 hardening pins — driver errors must degrade per the testing contract.

1. InMemoryCommandBus.dispatch_result — a handler raising a non-builtin
   driver error becomes Err(CommandError), never a raw raise.
2. InMemoryQueryBus.execute_result — a handler raising a non-builtin
   driver error becomes Err(<exception>), preserving the type.
3. CacheTestClient.get_cache_health — a failing health check reports
   "unhealthy", never "healthy".

Run with: pytest tests/unit/test_round33_hardening.py -v
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.testing.memory.cqrs import InMemoryCommandBus, InMemoryQueryBus



class _DriverError(Exception):
    """Stand-in for a driver/SDK error type (not RuntimeError/OSError)."""


class _Cmd:
    pass


class _Query:
    pass


class TestCommandBusResultContract:
    @pytest.mark.asyncio
    async def test_handler_driver_error_becomes_err(self) -> None:
        bus = InMemoryCommandBus()

        async def _handler(command: object) -> object:
            raise _DriverError("handler blew up")

        bus.register(_Cmd, _handler)

        result = await bus.dispatch_result(_Cmd())

        assert result.is_err()


class TestQueryBusResultContract:
    @pytest.mark.asyncio
    async def test_handler_driver_error_becomes_err_preserving_type(self) -> None:
        bus = InMemoryQueryBus()

        async def _handler(query: object) -> object:
            raise _DriverError("query blew up")

        bus.register(_Query, _handler)

        result = await bus.execute_result(_Query())

        assert result.is_err()
        assert isinstance(result.unwrap_err(), _DriverError)


class TestCacheHealthSemantics:
    @pytest.mark.asyncio
    async def test_failed_health_check_reports_unhealthy(self) -> None:
        from quadkit.testing.clients.cache.client_core import CacheTestClient

        client = CacheTestClient.__new__(CacheTestClient)
        client._cache_service = MagicMock()
        client.cache_service.health_check = AsyncMock(
            side_effect=_DriverError("health probe down")
        )

        health = await client.get_cache_health()

        assert health["status"] == "unhealthy"
