"""Raw mail transport and shared delivery store for queued delivery workers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.contracts.mailer.protocols import MailerProtocol
    from quadkit.contracts.notification.delivery import DeliveryStoreProtocol


@dataclass(frozen=True)
class MailerDeliveryRuntime:
    """Provider-owned runtime surface for asynchronous queued mail.

    ``MailerProtocol`` resolved by ordinary application services may be wrapped
    in inline retry behavior. The queued worker instead needs the raw configured
    transport plus the same persistent store, so retries are scheduled once by
    ``flush_retries`` rather than being nested inside the worker.
    """

    backend: MailerProtocol
    delivery_store: DeliveryStoreProtocol


__all__ = ["MailerDeliveryRuntime"]
