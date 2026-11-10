"""Explicit fixed-account inbox channel for the native delivery dispatcher."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import deepcopy
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from quadkit.contracts.mailer import MessageDeliveryReceipt
from quadkit.contracts.notification.errors import NotificationError
from quadkit.contracts.notification.inbox import InboxMessage
from quadkit.contracts.notification.types import DeliveryMessage
from quadkit.notification.inbox.idempotency import fingerprint, validate_key
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.auth.user import UserProtocol
    from quadkit.notification.inbox.service import InboxService


class InboxDeliveryChannel:
    """Bind inbox delivery to one server-configured, existing active account.

    The producer and recipient email configuration must be trusted server code,
    not action/query/body input. Each attempt resolves the account through the
    host's real user store; unknown/inactive/mismatched accounts fail closed.
    The immutable ``effect_key`` and server-resolved ``recipient_user_id``
    are required in the persisted envelope. Email reassignment cannot redirect
    an already queued notification to a newly created account.
    Retrying after inbox commit but before worker acknowledgement does not
    duplicate a message. There is deliberately no HTTP send route, fallback
    fixture user, implicit registration, or broadcast/recipient selection API.
    """

    channel = "inbox"

    def __init__(
        self,
        service: InboxService,
        lookup_recipient: Callable[[str], Awaitable[UserProtocol | None]],
        *,
        recipient_email: str,
    ) -> None:
        """Bind native services and a deployment-owned recipient lookup key."""
        if not isinstance(recipient_email, str) or not recipient_email.strip():
            raise ValueError("a server-configured recipient email is required")
        self._service = service
        self._lookup_recipient = lookup_recipient
        self._email = recipient_email.strip()

    async def prepare(
        self, key: str, subject: str, body: str, **metadata: Any
    ) -> Result[DeliveryMessage, NotificationError]:
        """Resolve and pin the configured account before durable enqueue.

        There is no recipient argument. Hosts must call this from trusted
        committed-state/command code, then persist the envelope using the native
        delivery store. Business writes and SQL enqueue may share one provider
        transaction; actual delivery runs only after commit. This method does
        not itself enqueue, publish, authorize the producer or start a worker.
        """
        validate_key(key)
        if {"effect_key", "recipient_user_id"} & metadata.keys():
            return Err(
                NotificationError(
                    "Inbox routing metadata is server-owned",
                    channel="inbox",
                    backend="inbox",
                )
            )
        fingerprint(InboxMessage.create("unresolved", subject, body, metadata=metadata))
        snapshot = deepcopy(metadata)
        user = await self._lookup_recipient(self._email)
        if (
            user is None
            or user.is_active is not True
            or not user.user_id.strip()
            or user.email != self._email
        ):
            return Err(
                NotificationError(
                    "Configured inbox recipient is unavailable",
                    channel="inbox",
                    backend="inbox",
                )
            )
        return Ok(
            DeliveryMessage(
                self.channel,
                self._email,
                subject,
                body,
                {**snapshot, "effect_key": key, "recipient_user_id": user.user_id},
            )
        )

    async def send(
        self, message: DeliveryMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Resolve the bound account and persist one immutable inbox effect.

        Storage exceptions propagate to the existing durable worker's retry
        path. Configuration/account/payload refusals return a native typed
        failure; the worker retains its bounded attempt/dead-letter policy.
        """
        message = replace(message, metadata=deepcopy(message.metadata))
        if message.channel != self.channel or message.recipient != self._email:
            return self._refuse("Inbox destination does not match server binding")
        key = message.metadata.get("effect_key")
        if not isinstance(key, str) or not key.strip():
            return self._refuse("Inbox delivery requires a server-owned effect_key")
        expected_user_id = message.metadata.get("recipient_user_id")
        if not isinstance(expected_user_id, str) or not expected_user_id.strip():
            return self._refuse(
                "Inbox delivery requires a server-resolved recipient_user_id"
            )
        user = await self._lookup_recipient(self._email)
        if (
            user is None
            or user.is_active is not True
            or not isinstance(user.user_id, str)
            or not user.user_id.strip()
            or user.email != self._email
            or user.user_id != expected_user_id
        ):
            return self._refuse("Configured inbox recipient is unavailable")
        try:
            receipt = await self._service.send_once(
                key, user.user_id, message.subject, message.body, **message.metadata
            )
        except (ValueError, TypeError):
            return self._refuse(
                "Inbox delivery intent is invalid or conflicts with its key"
            )
        return Ok(receipt)

    @staticmethod
    def _refuse(reason: str) -> Result[MessageDeliveryReceipt, NotificationError]:
        return Err(NotificationError(reason, channel="inbox", backend="inbox"))


__all__ = ["InboxDeliveryChannel"]
