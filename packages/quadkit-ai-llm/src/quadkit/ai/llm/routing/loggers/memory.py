"""In-memory inference logger for LLM routing.

Stores a bounded FIFO queue of ``InferenceLog`` entries in memory.
Suitable for development and single-process deployments.  State is lost
on process restart; use ``DatabaseInferenceLogger`` for production.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from quadkit.ai.llm.routing.types import InferenceLog

logger = get_logger(__name__)

__all__ = ["InMemoryInferenceLogger"]


class InMemoryInferenceLogger:
    """Bounded FIFO in-memory inference logger.

    Stores up to *max_size* ``InferenceLog`` entries.  When the limit is
    reached, the oldest entry is evicted before inserting the new one
    (FIFO eviction).

    Example:
        >>> inference_logger = InMemoryInferenceLogger(max_size=500)
        >>> await inference_logger.log(some_log)
        >>> recent = await inference_logger.get_recent(limit=10)
    """

    def __init__(self, max_size: int = 1000) -> None:
        """Initialise the in-memory inference logger.

        Args:
            max_size: Maximum number of log entries to retain.
        """
        self._max_size = max_size
        self._entries: list[InferenceLog] = []
        self._lock = asyncio.Lock()

    async def log(self, entry: InferenceLog) -> None:
        """Record one ``InferenceLog`` entry.

        Evicts the oldest entry when ``max_size`` is reached.

        Args:
            entry: :class:`~quadkit.ai.llm.routing.types.InferenceLog` instance.
        """
        async with self._lock:
            if len(self._entries) >= self._max_size:
                self._entries.pop(0)
            self._entries.append(entry)

    async def get_recent(self, limit: int = 100) -> list[InferenceLog]:
        """Return the most recent *limit* log entries (newest-first).

        Args:
            limit: Maximum number of entries to return.

        Returns:
            Reversed slice of the internal list (newest first).
        """
        async with self._lock:
            return list(reversed(self._entries[-limit:]))
