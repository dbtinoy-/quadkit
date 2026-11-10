"""In-memory workflow checkpoint store."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.logging.factory import get_logger

if TYPE_CHECKING:
    from quadkit.workflow.graph.state import WorkflowState

logger = get_logger(__name__)


class WorkflowCheckpoint:
    """In-memory checkpoint store for workflow states.

    Args:
        max_size: Maximum number of checkpoints to keep.
            Oldest entries are evicted once the limit is reached.
            0 means unlimited.
    """

    def __init__(self, max_size: int = 512) -> None:
        self._store: dict[str, dict[str, object]] = {}
        self._order: list[str] = []
        self._max_size = max_size

    def save(self, checkpoint_id: str, state: WorkflowState) -> None:
        """Persist a snapshot of state under checkpoint_id.

        Args:
            checkpoint_id: Unique identifier for this checkpoint.
            state: Workflow state to snapshot.
        """
        snapshot = state.as_dict()
        if checkpoint_id in self._store:
            self._store[checkpoint_id] = snapshot
            logger.debug("checkpoint_updated")
            return

        if self._max_size and len(self._order) >= self._max_size:
            evicted = self._order.pop(0)
            del self._store[evicted]
            logger.debug("checkpoint_evicted")

        self._store[checkpoint_id] = snapshot
        self._order.append(checkpoint_id)
        logger.debug("checkpoint_saved")

    def load(self, checkpoint_id: str) -> dict[str, object] | None:
        """Retrieve the state snapshot for checkpoint_id.

        Args:
            checkpoint_id: Identifier to look up.

        Returns:
            The raw state dict if found, otherwise None.
        """
        snapshot = self._store.get(checkpoint_id)
        if snapshot is None:
            logger.debug("checkpoint_miss")
        else:
            logger.debug("checkpoint_loaded")
        return snapshot

    def delete(self, checkpoint_id: str) -> bool:
        """Remove a checkpoint entry.

        Args:
            checkpoint_id: Identifier to remove.

        Returns:
            True if an entry was removed, False if not found.
        """
        if checkpoint_id not in self._store:
            return False
        del self._store[checkpoint_id]
        try:
            self._order.remove(checkpoint_id)
        except ValueError:
            pass
        logger.debug("checkpoint_deleted")
        return True

    def __len__(self) -> int:
        """Return the number of active checkpoints."""
        return len(self._store)

    def __contains__(self, checkpoint_id: str) -> bool:
        """Check whether checkpoint_id has been saved."""
        return checkpoint_id in self._store


__all__ = ["WorkflowCheckpoint"]
