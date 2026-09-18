"""Integration-event and webhook signature protocols."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.events.protocols import (
    AggregateFactoryProtocol,
    CommandBusProtocol,
    CommandHandlerProtocol,
    DomainEventPublisherProtocol,
    EventBusProtocol,
    EventHandlerProtocol,
    EventMiddlewareProtocol,
    EventSourcedReadRepositoryProtocol,
    EventSourcedRepositoryProtocol,
    EventStoreProtocol,
    IntegrationEventProtocol,
    MultiEventHandlerProtocol,
    ProjectionProtocol,
    PubSubProtocol,
    QueryBusProtocol,
    QueryHandlerProtocol,
    SnapshotStoreProtocol,
    WebhookSignatureVerifierProtocol,
)




class TestIntegrationEventProtocol:
    """Tests for IntegrationEventProtocol."""

    def test_has_required_attributes(self) -> None:
        """Test protocol has required attributes."""

        class Event:
            event_id: str = "evt-1"
            event_type: str = "TestEvent"
            source_service: str = "test-service"
            correlation_id: str | None = None
            causation_id: str | None = None
            payload: dict[str, Any] = {}
            occurred_at: Any = None

        event = Event()
        assert event.event_id == "evt-1"
        assert event.event_type == "TestEvent"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Event:
            event_id: str = ""
            event_type: str = ""
            source_service: str = ""
            correlation_id: str | None = None
            causation_id: str | None = None
            payload: dict = {}
            occurred_at: Any = None

        assert isinstance(Event(), IntegrationEventProtocol)


class TestWebhookSignatureVerifierProtocol:
    """Tests for WebhookSignatureVerifierProtocol."""

    def test_has_verify_method(self) -> None:
        """Test protocol has verify method."""

        class Verifier:
            def verify(
                self,
                payload: bytes,
                signature: str,
                secret: str,
            ) -> bool:
                return True

        verifier = Verifier()
        result = verifier.verify(b"payload", "signature", "secret")
        assert result is True

    def test_has_compute_signature_method(self) -> None:
        """Test protocol has compute_signature method."""

        class Verifier:
            def compute_signature(self, payload: bytes, secret: str) -> str:
                return "computed_signature"

        verifier = Verifier()
        result = verifier.compute_signature(b"payload", "secret")
        assert result == "computed_signature"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Verifier:
            def verify(self, payload: bytes, signature: str, secret: str) -> bool:
                return False

            def compute_signature(self, payload: bytes, secret: str) -> str:
                return ""

        assert isinstance(Verifier(), WebhookSignatureVerifierProtocol)
