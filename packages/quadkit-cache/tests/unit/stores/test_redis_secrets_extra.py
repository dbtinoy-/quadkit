"""Focused tests for the Redis secret store lifecycle."""

from __future__ import annotations

import pytest

from quadkit.cache.stores.redis_secrets import RedisSecretStore


class TestRedisSecretStoreClose:
    """close() releases the Redis client pool."""

    class _RecordingClient:
        def __init__(self) -> None:
            self.aclose_calls = 0

        async def aclose(self) -> None:
            self.aclose_calls += 1

    @pytest.mark.asyncio
    async def test_close_closes_injected_client_and_clears_reference(self) -> None:
        client = self._RecordingClient()
        store = RedisSecretStore(url="redis://x", client=client)
        await store.close()
        assert client.aclose_calls == 1
        assert store._client is None

    @pytest.mark.asyncio
    async def test_close_without_client_is_noop(self) -> None:
        store = RedisSecretStore(url="redis://x")
        await store.close()
        assert store._client is None

    @pytest.mark.asyncio
    async def test_close_with_sync_close_fallback(self) -> None:
        class _SyncCloseClient:
            def __init__(self) -> None:
                self.close_calls = 0

            def close(self) -> None:
                self.close_calls += 1

        client = _SyncCloseClient()
        store = RedisSecretStore(url="redis://x", client=client)
        await store.close()
        assert client.close_calls == 1
        assert store._client is None
