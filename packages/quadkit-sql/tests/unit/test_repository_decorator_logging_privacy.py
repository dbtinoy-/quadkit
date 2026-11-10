"""Repository decorator logs must not expose error text or entity keys."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import quadkit.sql.repositories.decorators as decorators_module
from quadkit.sql.repositories.decorators import cacheable, timed


@pytest.mark.asyncio
async def test_timed_logs_only_the_safe_exception_type(monkeypatch) -> None:
    private_error = "token=secret at /srv/private/tenant-42"
    logger = MagicMock()
    monkeypatch.setattr(decorators_module, "logger", logger)

    @timed()
    async def failing_operation() -> None:
        raise RuntimeError(private_error)

    with pytest.raises(RuntimeError, match="token=secret"):
        await failing_operation()

    logged = repr(logger.mock_calls)
    assert "RuntimeError" in logged
    assert "token=secret" not in logged
    assert "/srv/private/tenant-42" not in logged


@pytest.mark.asyncio
async def test_cache_logs_do_not_include_entity_key(monkeypatch) -> None:
    private_user_id = "private-user-7282"
    logger = MagicMock()
    monkeypatch.setattr(decorators_module, "logger", logger)
    cache = MagicMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()

    class Repository:
        @cacheable(ttl=60, key_prefix="user.lookup")
        async def get(self, user_id: str) -> dict[str, str]:
            return {"user_id": user_id}

    repository = Repository()
    repository.cache = cache
    assert await repository.get(private_user_id) == {"user_id": private_user_id}

    logged = repr(logger.mock_calls)
    assert "user.lookup" in logged
    assert private_user_id not in logged
