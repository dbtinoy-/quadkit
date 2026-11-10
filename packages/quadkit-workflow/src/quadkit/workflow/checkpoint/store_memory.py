"""In-memory content-addressed checkpoint store for testing."""

from __future__ import annotations

from collections.abc import Sequence

from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
)

__all__ = ["InMemoryContentCheckpointStore"]


class InMemoryContentCheckpointStore:
    """In-memory dict-backed checkpoint store for testing."""

    def __init__(self) -> None:
        self._store: dict[str, ContentCheckpointEntry] = {}

    async def get(self, key: ContentCheckpointKey) -> ContentCheckpointEntry | None:
        return self._store.get(key.as_str())

    async def set(
        self, key: ContentCheckpointKey, entry: ContentCheckpointEntry
    ) -> None:
        self._store[key.as_str()] = entry

    async def evict(self, key: ContentCheckpointKey) -> None:
        self._store.pop(key.as_str(), None)

    async def list_by_stage(
        self,
        stage_id: str,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> Sequence[ContentCheckpointKey]:
        results: list[ContentCheckpointKey] = []
        for key_str in self._store:
            parts = key_str.split("|", 3)
            if len(parts) >= 2 and parts[0] == stage_id:
                if tenant_id is not None and parts[1] != tenant_id:
                    continue
                if len(parts) >= 4:
                    results.append(
                        ContentCheckpointKey(
                            stage_id=parts[0],
                            tenant_id=parts[1] if parts[1] != "_global" else None,
                            input_hash=bytes.fromhex(parts[2]),
                            config_hash=bytes.fromhex(parts[3]),
                        )
                    )
        return results[:limit]
