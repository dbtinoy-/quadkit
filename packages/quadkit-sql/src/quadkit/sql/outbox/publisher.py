"""Background outbox publisher that polls pending events and publishes them."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.concurrency.task_utils import create_tracked_task
from quadkit.contracts.data.outbox import OutboxStoreProtocol
from quadkit.logging import get_logger
from quadkit.serialization import loads_str as json_loads

if TYPE_CHECKING:
    from collections.abc import Mapping

    from quadkit.contracts.domain.events import DomainEvent

logger = get_logger(__name__)


class OutboxPublisher:
    """Polls outbox store and publishes pending events to the event bus.

    The relay half of the transactional outbox: a service wrote the event
    in the same transaction as its business row; this loop reads what was
    committed and hands it to the bus. A row is marked delivered only after
    the bus accepted the event, so a crash between the two re-delivers (at
    least once) rather than loses.

    How a row becomes an event again:

    * ``event_types`` maps the stored ``event_type`` name to its class and
      the row is rebuilt with ``from_dict`` and passed to ``publish`` —
      the only way to reach :class:`quadkit.events.buses.EventBusImpl`,
      whose subscribers are keyed by class.
    * A bus that offers ``publish_raw(event_type=..., payload=...)`` is
      used as-is for names not in the map.
    * Otherwise the row is marked failed with a reason, instead of a
      ``publish_raw`` ``AttributeError`` on every poll.

    A ``publish`` that returns a ``Result`` is checked: ``Err`` is a
    failure, not a delivery.

    Args:
        store: The outbox store to poll.
        event_bus: Event bus to publish events to.
        poll_interval: Seconds between polling cycles. Defaults to 5.
        batch_size: Maximum events per cycle. Defaults to 50.
        event_types: Stored type name → event class, for ``publish``.
    """

    def __init__(
        self,
        store: OutboxStoreProtocol,
        event_bus: Any,
        poll_interval: float = 5.0,
        batch_size: int = 50,
        event_types: Mapping[str, type[DomainEvent]] | None = None,
    ) -> None:
        self._store = store
        self._event_bus = event_bus
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._event_types: dict[str, type[DomainEvent]] = dict(event_types or {})
        self._tasks: set[asyncio.Task[Any]] = set()
        self._running = False

    def register(self, *event_types: type[DomainEvent]) -> None:
        """Teach the relay more event classes, keyed by class name."""
        for event_type in event_types:
            self._event_types[event_type.__name__] = event_type

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

    async def drain(self) -> int:
        """Relay everything pending right now. Returns the number of rows seen.

        For tests and for shutdown: a caller that just committed an outbox
        row and wants it on the bus without waiting a poll interval.
        """
        total = 0
        while True:
            seen = await self._process_batch()
            total += seen
            if seen < self._batch_size:
                return total

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                await self._process_batch()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("outbox_poll_error", exc_info=exc)
            await asyncio.sleep(self._poll_interval)

    async def _publish(self, row: Mapping[str, Any]) -> None:
        """Publish one stored row, raising on anything short of acceptance."""
        payload = json_loads(row["payload"])
        event_type = self._event_types.get(row["event_type"])
        if event_type is not None:
            result = await self._event_bus.publish(event_type.from_dict(payload))
        elif hasattr(self._event_bus, "publish_raw"):
            result = await self._event_bus.publish_raw(
                event_type=row["event_type"], payload=payload
            )
        else:
            msg = (
                f"no event class registered for outbox event_type {row['event_type']!r} "
                "and the bus has no publish_raw"
            )
            raise LookupError(msg)
        if getattr(result, "is_err", None) is not None and result.is_err():
            error = result.unwrap_err()
            raise RuntimeError(str(error)) from (
                error if isinstance(error, BaseException) else None
            )

    async def _process_batch(self) -> int:
        """Process one batch of pending events. Returns count processed."""
        pending = await self._store.fetch_pending(limit=self._batch_size)
        if not pending:
            return 0
        for row in pending:
            try:
                await self._publish(row)
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
