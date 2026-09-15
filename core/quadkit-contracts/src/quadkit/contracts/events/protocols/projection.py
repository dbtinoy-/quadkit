"""Projection, PubSub, integration, and webhook protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime


@runtime_checkable
class ProjectionProtocol(Protocol):
    """ProjectionProtocol protocol for building read models from events."""

    def apply(self, event: Any) -> None:
        """Apply an event to the projection state.

        Args:
            event: Domain event to apply.
        """
        ...


@runtime_checkable
class PubSubProtocol(Protocol):
    """Protocol for publish/subscribe backends.

    Implementations must support publishing messages to topics and
    subscribing handlers to receive messages from topics.
    """

    async def publish(self, topic: str, data: Any) -> None:
        """Publish *data* to *topic*."""
        ...

    async def subscribe(
        self,
        topic: str,
        handler: Any,
    ) -> None:
        """Subscribe *handler* to receive messages from *topic*."""
        ...

    async def unsubscribe(self, topic: str, handler: Any) -> None:
        """Remove *handler* subscription from *topic*."""
        ...


@runtime_checkable
class IntegrationEventProtocol(Protocol):
    """Protocol formalising the bridge between domain events and transactional messaging.

    Any event intended for cross-service communication should satisfy this
    protocol.  Implementations carry all metadata required for reliable,
    idempotent delivery across bounded-context boundaries.

    Attributes:
        event_id: Unique, stable identifier for this event instance (e.g. a UUID4
            string).  Used by consumers for deduplication.
        event_type: The event class name or type discriminator string.  Consumers
            use this to route / deserialise the ``payload``.
        source_service: The bounded context or service that emitted this event
            (e.g. ``"order-service"``).
        correlation_id: Optional distributed-trace correlation identifier that
            links this event to a broader request chain.  ``None`` when tracing
            is not active.
        causation_id: Optional identifier of the event or command that directly
            caused this event to be emitted.  ``None`` for root events.
        payload: The event data as a JSON-serialisable dictionary.  Must not
            contain non-serialisable types (e.g. ``datetime`` objects must be
            ISO-formatted strings).
        occurred_at: UTC timestamp recording when the event occurred in the
            source service.

    Example::

        class UserRegisteredIntegrationEvent:
            event_id: str = field(default_factory=lambda: str(uuid4()))
            event_type: str = "UserRegistered"
            source_service: str = "identity-service"
            correlation_id: str | None = None
            causation_id: str | None = None
            payload: dict[str, Any] = field(default_factory=dict)
            occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    """

    event_id: str
    event_type: str
    source_service: str
    correlation_id: str | None
    causation_id: str | None
    payload: dict[str, Any]
    occurred_at: datetime


@runtime_checkable
class WebhookSignatureVerifierProtocol(Protocol):
    """Verifies the authenticity of inbound webhook payloads.

    Implementations must provide both a verification method and a signature
    computation method so callers can independently validate or generate
    signatures without exposing the underlying algorithm.

    The canonical implementation is HMAC-SHA256, but any MAC or asymmetric
    scheme that fulfils this protocol is acceptable.

    Typical usage::

        verifier = HMACWebhookVerifier()
        if not verifier.verify(payload=body, signature=sig_header, secret=secret):
            raise PermissionError("Invalid webhook signature")
    """

    def verify(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """Return ``True`` when the signature matches the payload.

        Implementations must use a constant-time comparison to prevent
        timing side-channel attacks.

        Args:
            payload: Raw request body bytes.
            signature: Signature string as received in the request header
                (may include algorithm prefix such as ``"sha256=..."``).
            secret: Shared secret used to compute the expected signature.

        Returns:
            ``True`` if the signature is valid, ``False`` otherwise.
        """
        ...

    def compute_signature(self, payload: bytes, secret: str) -> str:
        """Compute the expected signature for *payload* using *secret*.

        Args:
            payload: Raw request body bytes.
            secret: Shared secret.

        Returns:
            Hex-encoded signature string in the same format that
            :meth:`verify` expects as input.
        """
        ...
