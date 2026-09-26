"""Tests for tag-based cache invalidation.

Covers the P2 memory-management fix: the in-memory tag index must be bounded
so a long-running process cannot accumulate stale tag→key mappings indefinitely.
"""

from __future__ import annotations

from collections import OrderedDict

import pytest

from quadkit.cache.service.invalidation import InvalidationMixin

# ---------------------------------------------------------------------------
# Minimal host class that satisfies InvalidationMixin's duck-type requirements.
# ---------------------------------------------------------------------------

class _FakeHost(InvalidationMixin):
    """Minimal host that wires up the tag index and stubs set / delete_many."""

    def __init__(self, max_tags: int = 10_000) -> None:
        self._tag_index: OrderedDict[str, set[str]] = OrderedDict()
        self._max_tags: int = max_tags

    async def set(  # noqa: A003
        self,
        key: str,
        value: object,
        *,
        ttl: int | None = None,
        backend: str | None = None,
    ) -> bool:
        return True

    async def delete_many(
        self,
        keys: list[str],
        backend: str | None = None,
    ) -> int:
        return len(keys)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTagIndexBounded:
    """P2-tag-index-bound: tag index must evict oldest entries at capacity."""

    @pytest.mark.asyncio
    async def test_tag_index_evicts_oldest_when_at_capacity(self) -> None:
        """Adding a 4th tag when max_tags=3 must evict the oldest (tag-0)."""
        svc = _FakeHost(max_tags=3)

        for i in range(4):
            await svc.set_with_tags(f"key-{i}", f"val-{i}", [f"tag-{i}"])

        assert len(svc._tag_index) == 3, (
            f"Expected 3 tags (capacity), got {len(svc._tag_index)}"
        )
        assert "tag-0" not in svc._tag_index, "Oldest tag must be evicted"

    @pytest.mark.asyncio
    async def test_tag_index_does_not_evict_below_capacity(self) -> None:
        """When under capacity, no entries should be evicted."""
        svc = _FakeHost(max_tags=10)

        for i in range(5):
            await svc.set_with_tags(f"key-{i}", f"val-{i}", [f"tag-{i}"])

        assert len(svc._tag_index) == 5

    @pytest.mark.asyncio
    async def test_tag_index_is_ordered_dict(self) -> None:
        """P2: _tag_index must be an OrderedDict to support LRU eviction."""
        svc = _FakeHost(max_tags=10)
        assert isinstance(svc._tag_index, OrderedDict)

    @pytest.mark.asyncio
    async def test_recently_used_tag_is_not_evicted(self) -> None:
        """Re-using an existing tag moves it to the end; it must not be evicted."""
        svc = _FakeHost(max_tags=3)

        # Fill to capacity with tag-0, tag-1, tag-2
        for i in range(3):
            await svc.set_with_tags(f"key-{i}", f"val-{i}", [f"tag-{i}"])

        # Touch tag-0 again (moves it to end / most-recently-used)
        await svc.set_with_tags("key-touched", "val-touched", ["tag-0"])

        # Adding tag-3 should now evict tag-1 (oldest), not tag-0
        await svc.set_with_tags("key-3", "val-3", ["tag-3"])

        assert len(svc._tag_index) == 3
        assert "tag-0" in svc._tag_index, "Touched tag must survive eviction"
        assert "tag-1" not in svc._tag_index, "Oldest untouched tag must be evicted"

    @pytest.mark.asyncio
    async def test_invalidate_by_tag_still_works_after_eviction(self) -> None:
        """Invalidation on an evicted tag must return 0 gracefully."""
        svc = _FakeHost(max_tags=2)

        await svc.set_with_tags("key-0", "val-0", ["tag-0"])
        await svc.set_with_tags("key-1", "val-1", ["tag-1"])
        # Triggers eviction of tag-0
        await svc.set_with_tags("key-2", "val-2", ["tag-2"])

        count = await svc.invalidate_by_tag("tag-0")
        assert count == 0, "Evicted tag should return 0 deleted keys"
