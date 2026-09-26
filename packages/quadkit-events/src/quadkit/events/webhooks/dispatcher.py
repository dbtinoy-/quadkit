"""Outbound webhook fan-out dispatcher.

Delivers domain events to registered external HTTP endpoints with
cryptographic signing and configurable retry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quadkit import serialization as json
from quadkit.contracts.exceptions.resilience import RetryError
from quadkit.contracts.infra.resilience.models import RetryConfig
from quadkit.events.adapters.retry import retry as _retry_call
from quadkit.events.exceptions import WebhookDeliveryError
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.domain.events import DomainEvent
    from quadkit.contracts.events import (
        WebhookSignatureVerifierProtocol,
    )
    from quadkit.contracts.web.protocols import (  # type: ignore[attr-defined]
        HTTPClientProtocol,
    )

logger = get_logger(__name__)

_SIGNATURE_HEADER = "X-Webhook-Signature"
_EVENT_TYPE_HEADER = "X-Webhook-Event-Type"


@dataclass
class WebhookEndpoint:
    """An external endpoint registered to receive domain events.

    Attributes:
        url: HTTP(S) URL to POST events to.
        secret: Shared secret used to compute the HMAC signature.
        event_types: Set of event type names this endpoint subscribes to.
            When ``None``, all events are delivered.
    """

    url: str
    secret: str
    event_types: set[str] | None = field(default=None)

    def accepts(self, event: DomainEvent) -> bool:
        """Return ``True`` when this endpoint should receive *event*.

        Args:
            event: Domain event to test against the filter.

        Returns:
            ``True`` when ``event_types`` is ``None`` (all events) or the
            event's type name is contained in ``event_types``.
        """
        if self.event_types is None:
            return True
        return (event.event_type or type(event).__name__) in self.event_types


class WebhookDispatcher:
    """Delivers domain events to registered external webhook endpoints.

    Signs each outbound POST with a cryptographic signature via the injected
    ``WebhookSignatureVerifierProtocol`` so that receivers can verify
    authenticity.  Retries transient 5xx failures according to *retry_policy*.
    Delivery failures for one endpoint are logged and do not prevent fan-out
    to remaining endpoints.

    Example::

        dispatcher = WebhookDispatcher(
            http_client=http_client,
            signature_verifier=HMACWebhookVerifier(),
            retry_policy=RetryConfig(max_attempts=3),
        )
        await dispatcher.dispatch(user_created_event, registered_endpoints)
    """

    def __init__(
        self,
        http_client: HTTPClientProtocol,
        signature_verifier: WebhookSignatureVerifierProtocol,
        retry_policy: RetryConfig | None = None,
    ) -> None:
        """Initialise the dispatcher.

        Args:
            http_client: HTTP client used for outbound POST requests.
            signature_verifier: Used to compute the outbound HMAC signature
                included in ``X-Webhook-Signature``.
            retry_policy: Retry configuration; defaults to 3 attempts with
                exponential backoff when not provided.
        """
        self._http_client = http_client
        self._signature_verifier = signature_verifier
        self._retry_policy = retry_policy or RetryConfig(max_attempts=3)

    async def dispatch(
        self,
        event: DomainEvent,
        endpoints: list[WebhookEndpoint],
    ) -> None:
        """Sign and POST *event* to each eligible registered endpoint.

        Only endpoints whose ``event_types`` filter matches the event are
        delivered to.  Each delivery is retried per ``retry_policy`` on
        transient (5xx) failures.  Failures are logged but do not abort
        delivery to remaining endpoints.

        Args:
            event: Domain event to fan-out.
            endpoints: Registered endpoints to consider for delivery.
        """
        payload: bytes = json.dumps(event.to_dict())
        event_type = event.event_type or type(event).__name__
        for endpoint in endpoints:
            if not endpoint.accepts(event):
                continue
            await self._deliver_to(payload, event_type, endpoint)

    async def _deliver_to(
        self,
        payload: bytes,
        event_type: str,
        endpoint: WebhookEndpoint,
    ) -> None:
        """Deliver *payload* to a single *endpoint* with retry on transient errors.

        Args:
            payload: Serialised event bytes to POST.
            event_type: Human-readable event type name written to headers.
            endpoint: Target endpoint configuration.
        """
        signature = self._signature_verifier.compute_signature(payload, endpoint.secret)
        headers: dict[str, Any] = {
            "Content-Type": "application/json",
            _SIGNATURE_HEADER: signature,
            _EVENT_TYPE_HEADER: event_type,
        }

        async def _post() -> None:
            response = await self._http_client.post(
                endpoint.url,
                data=payload,
                headers=headers,
            )
            if response.status >= 500:
                raise WebhookDeliveryError(
                    url=endpoint.url,
                    status=response.status,
                    message=f"Webhook endpoint returned HTTP {response.status}",
                )

        try:
            await _retry_call(_post, config=self._retry_policy)
        except (WebhookDeliveryError, RetryError):
            logger.error(
                "webhook_delivery_failed",
                url=endpoint.url,
                event_type=event_type,
            )
        except (RuntimeError, OSError, ConnectionError, TimeoutError) as exc:
            logger.error(
                "webhook_delivery_error",
                url=endpoint.url,
                event_type=event_type,
                error=str(exc),
            )


__all__ = ["WebhookDispatcher", "WebhookEndpoint"]
