"""Retry worker for framework-owned queued notification deliveries."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.notification.delivery import DeliveryRecord
from quadkit.logging import get_logger
from quadkit.primitives import clock

if TYPE_CHECKING:
    from quadkit.contracts.notification.delivery import DeliveryStoreProtocol
    from quadkit.contracts.notification.protocols import DeliveryDispatcherProtocol

logger = get_logger(__name__)


def _retry_delay(attempt_number: int, base_delay: float, max_delay: float) -> float:
    """Compute capped exponential backoff for a failed attempt."""
    # ``int ** int`` is ``Any`` in typeshed, so the result is named as a float.
    return float(min(base_delay * (2 ** max(0, attempt_number - 1)), max_delay))


async def _record_failure(
    store: DeliveryStoreProtocol,
    record: DeliveryRecord,
    attempt_number: int,
    reason: str,
    *,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
) -> None:
    """Persist one failed attempt and schedule it or move it to dead letter."""
    await store.complete_attempt(
        record.delivery_id,
        attempt_number,
        outcome="failed",
        error=reason,
    )
    if attempt_number >= max_attempts:
        await store.mark_failed(record.delivery_id, reason=reason)
        logger.error(
            "delivery_dead_lettered",
            delivery_id=record.delivery_id,
            channel=record.message.channel,
            attempts=attempt_number,
            error=reason,
        )
        return

    delay = _retry_delay(attempt_number, base_delay, max_delay)
    await store.schedule_retry(record.delivery_id, delay)
    logger.warning(
        "delivery_retry_scheduled",
        delivery_id=record.delivery_id,
        channel=record.message.channel,
        attempt=attempt_number,
        delay_seconds=delay,
        error=reason,
    )


async def flush_retries(
    store: DeliveryStoreProtocol,
    dispatcher: DeliveryDispatcherProtocol,
    limit: int = 50,
    *,
    max_attempts: int = 5,
    base_delay: float = 60.0,
    max_delay: float = 3600.0,
    lease_seconds: float = 300.0,
) -> int:
    """Deliver due messages through the registered framework channel dispatcher.

    A conditional database lease prevents concurrent workers from sending the
    same row. Transport failures are isolated per message and scheduled with
    capped exponential backoff; exhausted rows become terminal dead letters.
    Database/store failures propagate so the scheduler can report a failed run.

    Args:
        store: Persistent delivery outbox.
        dispatcher: Channel dispatcher resolved from the application container.
        limit: Maximum due rows to inspect in this flush.
        max_attempts: Total attempts before terminal failure.
        base_delay: Delay before the first scheduled retry, in seconds.
        max_delay: Maximum backoff delay, in seconds.
        lease_seconds: Duration a worker owns a claimed row.

    Returns:
        Number of deliveries accepted by their channel during this flush.

    Raises:
        ValueError: If a retry/lease setting is outside its valid range.
    """
    if limit < 0:
        raise ValueError("limit must not be negative")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if base_delay <= 0 or max_delay <= 0 or lease_seconds <= 0:
        raise ValueError("retry delays and lease_seconds must be positive")

    due = await store.due_deliveries(limit)
    delivered = 0
    for record in due:
        if not await store.claim_delivery(record.delivery_id, lease_seconds):
            continue

        if record.attempts >= max_attempts:
            await store.mark_failed(
                record.delivery_id,
                reason=record.last_error or "maximum delivery attempts exhausted",
            )
            logger.error(
                "delivery_dead_lettered",
                delivery_id=record.delivery_id,
                channel=record.message.channel,
                attempts=record.attempts,
                error=record.last_error,
            )
            continue

        attempt_number = record.attempts + 1
        await store.record_attempt(
            record.delivery_id,
            recipient=record.message.recipient,
            subject=record.message.subject,
            attempt_number=attempt_number,
        )
        try:
            result = await dispatcher.send(record.message)
        except Exception as exc:  # noqa: BLE001 — isolate a single transport failure
            await _record_failure(
                store,
                record,
                attempt_number,
                f"{type(exc).__name__}: {exc}",
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
            )
            continue

        if result.is_ok():
            await store.complete_attempt(
                record.delivery_id,
                attempt_number,
                outcome="delivered",
            )
            await store.mark_delivered(record.delivery_id)
            delivered += 1
            logger.info(
                "delivery_accepted",
                delivery_id=record.delivery_id,
                channel=record.message.channel,
                attempt=attempt_number,
            )
            continue

        error = result.unwrap_err()
        reason = str(error)
        await _record_failure(
            store,
            record,
            attempt_number,
            reason,
            max_attempts=max_attempts,
            base_delay=base_delay,
            max_delay=max_delay,
        )

    logger.debug(
        "delivery_flush_completed",
        due=len(due),
        delivered=delivered,
        finished_at=clock.now().isoformat(),
    )
    return delivered


__all__ = ["flush_retries"]
