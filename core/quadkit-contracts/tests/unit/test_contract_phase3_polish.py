from __future__ import annotations

from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from quadkit.contracts.ai.vector import EmbeddingResult
from quadkit.contracts.infra.tasks.protocols import DLQProtocol


class _DLQImpl:
    async def add(
        self,
        message_id: str,
        payload: Any,
        reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        return None

    async def get(self, message_id: str) -> dict[str, Any] | None:
        return None

    async def retry(self, message_id: str) -> bool:
        return True

    async def purge(self, message_id: str) -> bool:
        return True

    async def clear(self) -> int:
        return 0

    async def size(self) -> int:
        return 0

    async def list_failed(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return []


def test_dlq_protocol_is_runtime_checkable() -> None:
    assert isinstance(_DLQImpl(), DLQProtocol)


def test_embedding_result_is_frozen() -> None:
    result = EmbeddingResult(vectors=[[0.1, 0.2]], model="test-model", tokens=2)

    with pytest.raises(FrozenInstanceError):
        result.tokens = 3  # type: ignore[misc]
