"""Quadkit CQRS Adapters.

This module provides adapters for integrating with external message queues
and event streaming platforms.

Supported Platforms:
- RabbitMQ: Message broker with topic routing
- Kafka: High-throughput event streaming
- Azure Service Bus: Cloud messaging service

Example:
    ```python
    from quadkit.events.adapters import RabbitMQAdapter, KafkaAdapter

    # RabbitMQ
    rabbitmq = RabbitMQAdapter(RabbitMQAdapterConfig(
        connection_string="amqp://localhost/",
        exchange_name="domain_events"
    ))
    await rabbitmq.connect()
    await rabbitmq.publish(event)

    # Kafka
    kafka = KafkaAdapter(KafkaAdapterConfig(
        bootstrap_servers=["localhost:9092"],
        topic_prefix="events."
    ))
    await kafka.connect()
    await kafka.publish(event)
    ```
"""

from __future__ import annotations

from quadkit.events.adapters.azure_servicebus import (
    AzureServiceBusAdapter,
    AzureServiceBusAdapterConfig,
)
from quadkit.events.adapters.base import (
    AdapterConfig,
    DefaultMessageSerializer,
    MessageAdapter,
    MessageSerializer,
)
from quadkit.events.adapters.kafka import (
    KafkaAdapter,
    KafkaAdapterConfig,
)
from quadkit.events.adapters.rabbitmq import (
    RabbitMQAdapter,
    RabbitMQAdapterConfig,
)

HAS_RABBITMQ = True
HAS_KAFKA = True
HAS_AZURE_SERVICEBUS = True


__all__ = [
    "HAS_AZURE_SERVICEBUS",
    "HAS_KAFKA",
    "HAS_RABBITMQ",
    "AdapterConfig",
    "DefaultMessageSerializer",
    "MessageAdapter",
    "MessageSerializer",
]

# Conditionally add optional exports
if HAS_RABBITMQ:
    __all__ += ["RabbitMQAdapter", "RabbitMQAdapterConfig"]

if HAS_KAFKA:
    __all__ += ["KafkaAdapter", "KafkaAdapterConfig"]

if HAS_AZURE_SERVICEBUS:
    __all__ += ["AzureServiceBusAdapter", "AzureServiceBusAdapterConfig"]
