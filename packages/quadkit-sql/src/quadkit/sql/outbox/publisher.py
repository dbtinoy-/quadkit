"""Background outbox publisher that polls pending events and publishes them."""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.contracts.data.outbox import OutboxStoreProtocol
from quadkit.logging import get_logger
from quadkit.serialization import loads_str as json_loads

logger = get_logger(__name__)


class OutboxPublisher:
    """Polls outbox store and publishes pending events to the event bus.

    Args:
        store: The outbox store to poll.
        event_bus: Event bus to publish events to.
        poll_interval: Seconds between polling cycles. Defaults to 5.
        batch_size: Maximum events per cycle. Defaults to 50.
    """

    def __init__(
        self,
        store: OutboxStoreProtocol,
        event_bus: Any,
        poll_interval: float = 5.0,
        batch_size: int = 50,
    ) -> None:
        self._store = store
        self._event_bus = event_bus
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._tasks: set[asyncio.Task[Any]] = set()
        self._running = False

    async def start(self) -> None:
        """Start the background polling loop."""
        self._running = True
        create_tracked_task(self._poll_loop(), self._tasks, name="outbox_publisher")
        logger.info("outbox_publisher_started", poll_interval=self._poll_interval)

    async def stop(self) -> None:
        """Stop the polling loop."""
        self._running = False
        for task in list(self._tasks):
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._process_batch()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("outbox_poll_error", exc_info=exc)
            await asyncio.sleep(self._poll_interval)

    async def _process_batch(self) -> int:
        """Process one batch of pending events. Returns count processed."""
        pending = await self._store.fetch_pending(limit=self._batch_size)
        if not pending:
            return 0
        for row in pending:
            try:
                payload = json_loads(row["payload"])
                await self._event_bus.publish_raw(
                    event_type=row["event_type"], payload=payload
                )
                await self._store.mark_delivered(row["id"])
            except Exception as exc:  # noqa: BLE001 — handler isolation: one event failure must not cascade to the rest of the batch
                try:
                    await self._store.mark_failed(row["id"], str(exc))
                except Exception as mark_exc:  # noqa: BLE001 — a failed dead-letter must not poison the rest of the batch; the event stays pending and is retried next cycle
                    logger.exception(
                        "outbox_dead_letter_failed",
                        event_id=row["id"],
                        error=str(mark_exc),
                    )
                logger.warning(
                    "outbox_event_failed", event_id=row["id"], error=str(exc)
                )
        logger.debug("outbox_batch_processed", count=len(pending))
        return len(pending)


__all__ = ["OutboxPublisher"]
