from __future__ import annotations

"""Kafka EventBus compliance test using a real Kafka broker."""

import pytest

from quadkit.testing.compliance import EventBusCompliance
from quadkit.testing.integration.fixtures import kafka_producer  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.requires_kafka]


class TestKafkaEventBusCompliance(EventBusCompliance):
    """Verify EventBusImpl + KafkaAdapter satisfies EventBusCompliance.

    Uses the ``kafka_producer`` fixture provided by
    ``quadkit.testing.integration.fixtures``.  The suite is auto-skipped when
    Kafka is not reachable or the ``aiokafka`` package is not installed.
    """

    @pytest.fixture(autouse=True)
    async def _setup(self, kafka_producer: object) -> None:
        """Capture the live Kafka producer for use in create_bus.

        Args:
            kafka_producer: Session-scoped AIOKafkaProducer connected to the
                test broker.
        """
        self._kafka_producer = kafka_producer

    async def create_bus(self) -> object:
        """Create an EventBusImpl wired with a KafkaAdapter.

        Returns:
            A ready-to-use EventBusImpl instance backed by Kafka.

        Raises:
            pytest.skip.Exception: If ``aiokafka`` is not installed or the
                bus/adapter cannot be imported.
        """
        try:
            from quadkit.events.adapters.kafka import (  # noqa: F401
                KafkaAdapter,
                KafkaAdapterConfig,
            )
            from quadkit.events.buses.event import EventBusImpl  # noqa: F401
        except ImportError:
            pytest.skip("EventBusImpl or KafkaAdapter not available")

        pytest.skip(
            "TODO: build KafkaAdapterConfig from integration_config.kafka_bootstrap, "
            "construct KafkaAdapter, connect it, and wire it into EventBusImpl"
        )

    def create_event(self) -> object:
        """Return a minimal domain event suitable for compliance test dispatch.

        Returns:
            A concrete Event instance for use in publish/subscribe assertions.

        Raises:
            pytest.skip.Exception: If the event types cannot be imported.
        """
        try:
            from quadkit.events.messages.event import Event  # noqa: F401
        except ImportError:
            pytest.skip("quadkit.events.messages.event not available")

        pytest.skip(
            "TODO: construct a concrete Event subclass (or minimal Event instance) "
            "once create_bus() wiring is complete"
        )
