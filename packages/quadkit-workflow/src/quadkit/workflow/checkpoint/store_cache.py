"""Cache-backed content-addressed checkpoint store.

Wraps ``CacheBackendProtocol`` from ``quadkit-cache`` to persist
content-addressed checkpoint entries with optional TTL.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Any

from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
)
from quadkit.serialization import dumps, loads

__all__ = ["CacheContentCheckpointStore"]


def _entry_to_dict(entry: ContentCheckpointEntry) -> dict[str, Any]:
    d = asdict(entry)
    d["completed_at"] = entry.completed_at.isoformat()
    return d


def _entry_from_dict(data: dict[str, Any]) -> ContentCheckpointEntry:
    data = dict(data)
    data["completed_at"] = datetime.fromisoformat(data["completed_at"])
    return ContentCheckpointEntry(**data)


class CacheContentCheckpointStore:
    """Content-addressed checkpoint store backed by a cache backend.

    Entries are JSON-serialized and stored with the checkpoint key string
    as the cache key. ``list_by_stage`` is not supported (cache backends
    lack prefix scanning).
    """

    def __init__(
        self,
        cache: CacheBackendProtocol,
        default_ttl: int | None = 86400,
    ) -> None:
        self._cache = cache
        self._default_ttl = default_ttl

    async def get(self, key: ContentCheckpointKey) -> ContentCheckpointEntry | None:
        result = await self._cache.get(key.as_str())
        if result.is_err():
            return None
        raw = result.unwrap()
        if raw is None:
            return None
        data = loads(raw)
        if not isinstance(data, dict):
            return None
        return _entry_from_dict(data)

    async def set(
        self, key: ContentCheckpointKey, entry: ContentCheckpointEntry
    ) -> None:
        data = dumps(_entry_to_dict(entry))
        await self._cache.set(key.as_str(), data, ttl=self._default_ttl)

    async def evict(self, key: ContentCheckpointKey) -> None:
        await self._cache.delete(key.as_str())

    async def list_by_stage(
        self,
        stage_id: str,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> Sequence[ContentCheckpointKey]:
        return []
