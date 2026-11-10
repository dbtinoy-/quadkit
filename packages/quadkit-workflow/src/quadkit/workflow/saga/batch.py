"""SagaProtocol batch processor with per-batch checkpointing.

Processes a collection of sagas in fixed-size batches and persists a
checkpoint to the ``SagaStoreProtocol`` after each batch so that a
crashed or interrupted run can be resumed from the last saved position
rather than reprocessed from the beginning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.workflow.protocols import SagaState, SagaStoreProtocol
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.workflow.saga.base import AbstractSaga

_logger = get_logger(__name__)

_CHECKPOINT_SUFFIX = ":checkpoint"


class SagaBatchProcessor:
    """Processes sagas in batches with per-batch checkpointing.

    After each batch is executed, the index of the last-processed saga
    is persisted to the ``SagaStoreProtocol`` under a key derived from
    the caller-supplied ``batch_id``.  A subsequent call to
    :meth:`process_batch` with the same ``batch_id`` will load this
    checkpoint and skip all already-processed sagas, enabling crash
    recovery without re-execution.

    Example:
        ```python
        processor = SagaBatchProcessor(store=saga_store, batch_size=50)

        # First run — or any run that starts from scratch
        processed = await processor.process_batch(sagas, batch_id="order-migration-v1")

        # On restart — skips completed sagas automatically
        processed = await processor.process_batch(sagas, batch_id="order-migration-v1")

        # Clean up once fully done
        await processor.clear_checkpoint("order-migration-v1")
        ```
    """

    def __init__(
        self,
        store: SagaStoreProtocol,
        *,
        batch_size: int = 50,
    ) -> None:
        """Initialise the batch processor.

        Args:
            store: Durable store used for checkpoint persistence and load.
            batch_size: Number of sagas to execute per checkpoint interval.
        """
        self._store = store
        self._batch_size = batch_size

    async def process_batch(
        self,
        sagas: list[AbstractSaga[Any]],
        batch_id: str,
    ) -> int:
        """Execute sagas in batches, saving a checkpoint after each batch.

        Loads the last checkpoint for ``batch_id`` (if any) and skips all
        sagas up to ``last_index`` before processing the remainder in slices
        of :attr:`_batch_size`.  A new checkpoint is persisted after every
        slice.

        Args:
            sagas: Ordered list of saga instances to execute.
            batch_id: Stable identifier used as the checkpoint key.  The
                same value must be passed on resume runs to continue from
                the last saved position.

        Returns:
            Number of sagas executed in this invocation.  Skipped sagas
            (those already covered by a previous checkpoint) are not counted.
        """
        start_index = await self._load_checkpoint(batch_id)

        if start_index > 0:
            _logger.info(
                "saga_batch.resuming",
                start_index=start_index,
                total=len(sagas),
            )

        count = 0
        i = start_index
        while i < len(sagas):
            batch = sagas[i : i + self._batch_size]

            for saga in batch:
                await saga.execute()
                count += 1

            i += len(batch)

            # Checkpoint after EACH batch so a crash can resume mid-run.
            await self._save_checkpoint(batch_id, i)
            _logger.debug(
                "saga_batch.checkpoint_saved",
                last_index=i,
                total=len(sagas),
            )

        _logger.info(
            "saga_batch.completed",
            processed=count,
            total=len(sagas),
        )
        return count

    async def clear_checkpoint(self, batch_id: str) -> None:
        """Remove the stored checkpoint, allowing the next run to start fresh.

        Args:
            batch_id: Checkpoint identifier to clear.
        """
        await self._store.delete(f"{batch_id}{_CHECKPOINT_SUFFIX}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _save_checkpoint(self, batch_id: str, last_index: int) -> None:
        """Persist the last-processed index for ``batch_id``."""
        await self._store.save(
            f"{batch_id}{_CHECKPOINT_SUFFIX}",
            SagaState.RUNNING,
            {"last_index": last_index},
        )

    async def _load_checkpoint(self, batch_id: str) -> int:
        """Load the last-processed index for ``batch_id``.

        Returns:
            The last-processed saga index, or ``0`` if no checkpoint exists.
        """
        record = await self._store.load(f"{batch_id}{_CHECKPOINT_SUFFIX}")
        if record is None:
            return 0
        _, data = record
        return int(data.get("last_index", 0))


__all__ = ["SagaBatchProcessor"]
