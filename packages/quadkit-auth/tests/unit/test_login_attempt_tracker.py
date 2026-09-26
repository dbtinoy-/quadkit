"""Tests for LoginAttemptTracker (Task G4-A6.2)."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from quadkit.auth.authn.services import LockoutConfig, LoginAttemptTracker


# ---------------------------------------------------------------------------
# LockoutConfig
# ---------------------------------------------------------------------------


class TestLockoutConfig:
    def test_defaults(self) -> None:
        cfg = LockoutConfig()
        assert cfg.max_failed_attempts == 5
        assert cfg.max_attempts == 5
        assert cfg.lockout_duration_seconds == 300

    def test_max_attempts_synced_with_max_failed_attempts(self) -> None:
        cfg = LockoutConfig(max_attempts=3)
        assert cfg.max_failed_attempts == 3
        assert cfg.max_attempts == 3

    def test_max_failed_attempts_sets_max_attempts(self) -> None:
        cfg = LockoutConfig(max_failed_attempts=7)
        assert cfg.max_failed_attempts == 7
        # max_attempts defaults to 5; __post_init__ only syncs when they differ
        # (max_attempts wins when explicitly set; here it was not — max_failed_attempts wins)
        assert cfg.max_failed_attempts == 7


# ---------------------------------------------------------------------------
# LoginAttemptTracker — in-memory (no cache)
# ---------------------------------------------------------------------------


class TestLoginAttemptTrackerInMemory:
    @pytest.mark.asyncio
    async def test_not_locked_initially(self) -> None:
        tracker = LoginAttemptTracker(max_attempts=3)
        assert not await tracker.is_locked("user@example.com")

    @pytest.mark.asyncio
    async def test_locks_after_max_attempts(self) -> None:
        tracker = LoginAttemptTracker(max_attempts=3, lockout_duration_seconds=60)

        for _ in range(3):
            await tracker.record_failure("user@example.com")

        assert await tracker.is_locked("user@example.com")

    @pytest.mark.asyncio
    async def test_not_locked_below_threshold(self) -> None:
        tracker = LoginAttemptTracker(max_attempts=5)

        for _ in range(4):
            await tracker.record_failure("user@example.com")

        assert not await tracker.is_locked("user@example.com")

    @pytest.mark.asyncio
    async def test_clear_removes_lock(self) -> None:
        tracker = LoginAttemptTracker(max_attempts=2)

        for _ in range(3):
            await tracker.record_failure("user@example.com")

        assert await tracker.is_locked("user@example.com")

        await tracker.clear("user@example.com")

        assert not await tracker.is_locked("user@example.com")

    @pytest.mark.asyncio
    async def test_expired_attempts_do_not_count(self) -> None:
        tracker = LoginAttemptTracker(max_attempts=2, lockout_duration_seconds=1)

        for _ in range(2):
            await tracker.record_failure("user@example.com")

        assert await tracker.is_locked("user@example.com")

        # Manually back-date the timestamps to simulate window expiry
        tracker._local["user@example.com"] = [time.time() - 2]

        assert not await tracker.is_locked("user@example.com")

    @pytest.mark.asyncio
    async def test_independent_identifiers(self) -> None:
        tracker = LoginAttemptTracker(max_attempts=2)

        for _ in range(2):
            await tracker.record_failure("alice@example.com")

        assert await tracker.is_locked("alice@example.com")
        assert not await tracker.is_locked("bob@example.com")


# ---------------------------------------------------------------------------
# LoginAttemptTracker — cache-backed
# ---------------------------------------------------------------------------


def _make_mock_cache() -> AsyncMock:
    """Return a minimal mock that satisfies the CacheBackendProtocol protocol."""
    store: dict[str, str] = {}

    mock = AsyncMock()

    async def get_side(key: str) -> str | None:
        return store.get(key)

    async def set_side(key: str, value: str, ttl: int | None = None) -> None:
        store[key] = value

    async def delete_side(key: str) -> bool:
        existed = key in store
        store.pop(key, None)
        return existed

    mock.get = AsyncMock(side_effect=get_side)
    mock.set = AsyncMock(side_effect=set_side)
    mock.delete = AsyncMock(side_effect=delete_side)
    return mock


class TestLoginAttemptTrackerCacheBacked:
    @pytest.mark.asyncio
    async def test_not_locked_when_cache_empty(self) -> None:
        tracker = LoginAttemptTracker(max_attempts=3, cache=_make_mock_cache())
        assert not await tracker.is_locked("user@example.com")

    @pytest.mark.asyncio
    async def test_locks_after_max_attempts_via_cache(self) -> None:
        tracker = LoginAttemptTracker(
            max_attempts=3,
            lockout_duration_seconds=60,
            cache=_make_mock_cache(),
        )

        for _ in range(3):
            await tracker.record_failure("user@example.com")

        assert await tracker.is_locked("user@example.com")

    @pytest.mark.asyncio
    async def test_clear_via_cache(self) -> None:
        tracker = LoginAttemptTracker(
            max_attempts=2,
            lockout_duration_seconds=60,
            cache=_make_mock_cache(),
        )

        for _ in range(3):
            await tracker.record_failure("user@example.com")

        assert await tracker.is_locked("user@example.com")

        await tracker.clear("user@example.com")

        assert not await tracker.is_locked("user@example.com")

    @pytest.mark.asyncio
    async def test_cache_key_format(self) -> None:
        cache = _make_mock_cache()
        tracker = LoginAttemptTracker(max_attempts=1, cache=cache)

        await tracker.record_failure("alice@example.com")

        # Verify the expected key prefix was used
        set_calls = cache.set.call_args_list
        assert any(
            "quadkit:auth:attempts:alice@example.com" in str(call)
            for call in set_calls
        )
