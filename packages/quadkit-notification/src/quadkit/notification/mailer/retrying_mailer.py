"""RetryingMailer — exponential back-off retry decorator for any MailerProtocol."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from quadkit.contracts.mailer.errors import MailerError
from quadkit.contracts.mailer.types import EmailMessage, MessageDeliveryReceipt
from quadkit.logging import get_logger
from quadkit.result import Err

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result
    from quadkit.contracts.mailer.protocols import MailerProtocol
    from quadkit.contracts.notification.delivery import DeliveryStoreProtocol

logger = get_logger(__name__)


class RetryingMailer:
    """A decorator that wraps any :class:`~quadkit.contracts.mailer.protocols.MailerProtocol`
    with exponential back-off retry and persistent delivery tracking.

    Each send is assigned a stable ``delivery_id`` (UUID4). Every attempt is
    recorded via :class:`~quadkit.contracts.notification.delivery.DeliveryStoreProtocol`
    so that delivery history is preserved for auditing and dead-letter inspection.

    Retry behaviour:
    - Retries only on *raised* exceptions (infrastructure failures: SMTP timeouts,
      network errors, auth failures). These are the recoverable transient failures
      the retry pattern targets.
    - ``Err(MailerError)`` returns from the inner mailer are *not* retried — they
      represent expected terminal delivery failures (bounced, rejected) per the
      ``MailerProtocol`` contract.
    - After exhausting all attempts the final failure is logged, recorded as
      ``mark_failed(final=True)``, and returned as ``Err(MailerError)`` — never
      raised — to prevent cascading failures in notification flows.

    Args:
        inner: The underlying :class:`~quadkit.contracts.mailer.protocols.MailerProtocol`
            implementation to delegate to.
        delivery_store: Persistent store for delivery attempt tracking.
        max_attempts: Maximum number of send attempts. Defaults to ``3``.
        base_delay: Seconds to wait before the first retry. Each subsequent
            retry doubles the delay (exponential back-off). Defaults to ``1.0``.
    """

    def __init__(
        self,
        inner: MailerProtocol,
        delivery_store: DeliveryStoreProtocol,
        max_attempts: int = 3,
        base_delay: float = 1.0,
    ) -> None:
        self._inner = inner
        self._delivery_store = delivery_store
        self._max_attempts = max_attempts
        self._base_delay = base_delay

    async def send(
        self,
        message: EmailMessage,
    ) -> Result[MessageDeliveryReceipt, MailerError]:
        """Send an email with exponential back-off retry.

        Conforms to :class:`~quadkit.contracts.mailer.protocols.MailerProtocol`.

        Args:
            message: The fully-formed email message to deliver.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` on acceptance by the backend.
            ``Err(MailerError)`` when all attempts are exhausted or the inner
            mailer returns a terminal delivery failure.
        """
        # Persist the pending delivery so the later mark_delivered /
        # mark_failed / record_attempt calls have a row to update.
        delivery_id = await self._delivery_store.create_pending(message)
        lease_seconds = max(
            300.0,
            sum(
                self._base_delay * (2 ** (attempt - 1))
                for attempt in range(1, self._max_attempts)
            )
            + 30.0,
        )
        if not await self._delivery_store.claim_delivery(delivery_id, lease_seconds):
            raise RuntimeError("newly created mail delivery could not be claimed")
        recipient = ", ".join(message.to)
        last_exc: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            await self._delivery_store.record_attempt(
                delivery_id=delivery_id,
                recipient=recipient,
                subject=message.subject,
                attempt_number=attempt,
            )
            try:
                result: Result[
                    MessageDeliveryReceipt, MailerError
                ] = await self._inner.send(message)
            except Exception as exc:
                last_exc = exc
                await self._delivery_store.complete_attempt(
                    delivery_id, attempt, outcome="failed", error=str(exc)
                )
                logger.warning(
                    "mail_attempt_failed",
                    delivery_id=delivery_id,
                    recipient=recipient,
                    attempt=attempt,
                    max_attempts=self._max_attempts,
                    error=str(exc),
                )
                if attempt < self._max_attempts:
                    delay = self._base_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(delay)
                continue

            if result.is_ok():
                await self._delivery_store.complete_attempt(
                    delivery_id, attempt, outcome="delivered"
                )
                await self._delivery_store.mark_delivered(delivery_id)
                logger.info(
                    "mail_delivered",
                    delivery_id=delivery_id,
                    recipient=recipient,
                    attempt=attempt,
                )
                return result

            # Err(MailerError) is an expected terminal refusal per MailerProtocol.
            mailer_err = result.unwrap_err()
            await self._delivery_store.complete_attempt(
                delivery_id,
                attempt,
                outcome="failed",
                error=str(mailer_err),
            )
            await self._delivery_store.mark_failed(
                delivery_id=delivery_id,
                reason=str(mailer_err),
                final=True,
            )
            logger.warning(
                "mail_delivery_rejected",
                delivery_id=delivery_id,
                recipient=recipient,
                attempt=attempt,
                reason=str(mailer_err),
            )
            return result

        reason = str(last_exc) if last_exc else "unknown"
        await self._delivery_store.mark_failed(
            delivery_id=delivery_id,
            reason=reason,
            final=True,
        )
        logger.error(
            "mail_delivery_failed",
            delivery_id=delivery_id,
            recipient=recipient,
            total_attempts=self._max_attempts,
            reason=reason,
        )
        return Err(
            MailerError(
                f"Delivery failed after {self._max_attempts} attempt(s): {reason}",
                backend="retrying",
            )
        )


__all__ = ["RetryingMailer"]
