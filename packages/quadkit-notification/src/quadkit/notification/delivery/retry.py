"""DeferredRetryMailer — schedules mail retries instead of sleeping in-process."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.notification.delivery.exceptions import PermanentDeliveryFailure
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.notification.delivery import DeliveryStoreProtocol

logger = get_logger(__name__)


class DeferredRetryMailer:
    """Schedule mail failures for the framework's durable retry worker.

    It wraps a raw mail backend rather than ``MailerProtocol`` so inline and
    deferred retry policies cannot accidentally nest.

    Args:
        backend: Raw backend with an async ``send`` method returning ``Result``.
        store: Durable delivery store for state and attempt history.
        max_retries: Total attempts for the paired ``flush_retries`` worker.
            Pass this value to the worker's ``max_attempts`` setting.
        base_delay: Base delay for capped exponential backoff. Pass the same
            value to the worker so the first deferred interval matches.
    """

    def __init__(
        self,
        backend: Any,
        store: DeliveryStoreProtocol,
        max_retries: int = 5,
        base_delay: float = 60.0,
    ) -> None:
        self._backend = backend
        self._store = store
        self._max_retries = max_retries
        self._base_delay = base_delay

    @property
    def backend(self) -> Any:
        """Return the raw mail backend used by the scheduled worker."""
        return self._backend

    @property
    def store(self) -> DeliveryStoreProtocol:
        """Return the delivery store used by this wrapper."""
        return self._store

    @property
    def max_retries(self) -> int:
        """Return the total attempts to configure on ``flush_retries``."""
        return self._max_retries

    @property
    def base_delay(self) -> float:
        """Return the first retry delay to configure on ``flush_retries``."""
        return self._base_delay

    async def send(self, message: Any) -> Result[str, PermanentDeliveryFailure]:
        """Attempt one send and persist the outcome or scheduled retry.

        Args:
            message: Email message passed to the raw backend.

        Returns:
            ``Ok(delivery_id)`` on acceptance or when a retry is scheduled;
            ``Err(PermanentDeliveryFailure)`` when the first failure is terminal
            under ``max_retries``. Later failures are terminalized by the worker.
        """
        if self._max_retries < 1:
            raise ValueError("max_retries must be at least 1")
        if self._base_delay <= 0:
            raise ValueError("base_delay must be positive")
        delivery_id = await self._store.create_pending(message)
        claimed = await self._store.claim_delivery(delivery_id)
        if not claimed:
            raise RuntimeError("newly created delivery could not be claimed")

        recipient_value = getattr(message, "to", None)
        recipient = ", ".join(recipient_value) if recipient_value else ""
        subject = str(getattr(message, "subject", ""))
        attempt_number = 1
        await self._store.record_attempt(
            delivery_id, recipient, subject, attempt_number
        )

        try:
            result = await self._backend.send(message)
        except Exception as exc:  # noqa: BLE001 — persist transport faults for retry
            reason = f"{type(exc).__name__}: {exc}"
            await self._store.complete_attempt(
                delivery_id, attempt_number, outcome="failed", error=reason
            )
            return await self._schedule_or_fail(delivery_id, attempt_number, reason)

        if result.is_ok():
            await self._store.complete_attempt(
                delivery_id, attempt_number, outcome="delivered"
            )
            await self._store.mark_delivered(delivery_id)
            logger.info("mail_delivered", delivery_id=delivery_id)
            return Ok(delivery_id)

        error = str(result.unwrap_err())
        await self._store.complete_attempt(
            delivery_id, attempt_number, outcome="failed", error=error
        )
        return await self._schedule_or_fail(delivery_id, attempt_number, error)

    async def _schedule_or_fail(
        self, delivery_id: str, attempt_number: int, reason: str
    ) -> Result[str, PermanentDeliveryFailure]:
        """Persist the deferred retry or terminal failure."""
        if attempt_number < self._max_retries:
            delay = self._base_delay * (2 ** (attempt_number - 1))
            await self._store.schedule_retry(delivery_id, delay)
            logger.warning(
                "mail_delivery_retry_scheduled",
                delivery_id=delivery_id,
                attempt=attempt_number,
                delay_seconds=delay,
                error=reason,
            )
            return Ok(delivery_id)

        await self._store.mark_failed(delivery_id, reason=reason)
        logger.error(
            "mail_delivery_permanently_failed",
            delivery_id=delivery_id,
            attempts=attempt_number,
            error=reason,
        )
        return Err(PermanentDeliveryFailure(delivery_id))


__all__ = ["DeferredRetryMailer"]
