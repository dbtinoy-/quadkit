"""Adapter wirer functions for Kafka and RabbitMQ.

These functions create, connect, and bridge adapters to the EventBusProtocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import BootContainerProtocol
    from quadkit.events.config import EventsConfig

logger = get_logger(__name__)


async def wire_kafka(
    config: EventsConfig,
    event_bus: Any,
    container: BootContainerProtocol,
) -> None:
    """Create a KafkaAdapter, connect it, and bridge it to the EventBusProtocol.

    Args:
        config: The EventsConfig instance.
        event_bus: The resolved EventBusProtocol instance.
        container: The DI container resolver.
    """
    from quadkit.events.adapters.kafka import (
        KafkaAdapter,
        KafkaAdapterConfig,
    )

    cfg = config.kafka
    if cfg is None:
        logger.warning("events.kafka_adapter_skipped", reason="No kafka config")
        return
    adapter_config = KafkaAdapterConfig(
        connection_string=cfg.bootstrap_servers,
        topic_prefix=cfg.topic_prefix + ".",
        group_id=cfg.consumer_group,
        auto_offset_reset=cfg.auto_offset_reset,
        enable_auto_commit=cfg.enable_auto_commit,
    )
    adapter = KafkaAdapter(config=adapter_config)
    try:
        await adapter.connect()
    except Exception as exc:  # noqa: BLE001 — optional wiring: any connect failure logs and skips, never crashes startup
        logger.warning("events.kafka_adapter_connect_failed", reason=str(exc))
        return

    # Outbound: EventBusProtocol → Kafka
    async def _forward_to_kafka(event: Any) -> None:
        try:
            await adapter.publish(event)
        except Exception as exc:  # noqa: BLE001 — forward failures must not break the bus
            logger.warning("events.kafka_forward_failed", reason=str(exc))

    event_bus.subscribe_all(_forward_to_kafka)

    # Register singleton so callers can resolve KafkaAdapter from container
    try:
        container.singleton(KafkaAdapter, adapter)
    except Exception:  # noqa: BLE001 — container may already be frozen
        pass  # container may already be frozen

    logger.info("events.kafka_adapter_wired", servers=cfg.bootstrap_servers)


async def wire_rabbitmq(
    config: EventsConfig,
    event_bus: Any,
    container: BootContainerProtocol,
) -> None:
    """Create a RabbitMQAdapter, connect it, and bridge it to the EventBusProtocol.

    Args:
        config: The EventsConfig instance.
        event_bus: The resolved EventBusProtocol instance.
        container: The DI container resolver.
    """
    from quadkit.events.adapters.rabbitmq import (
        RabbitMQAdapter,
        RabbitMQAdapterConfig,
    )

    cfg = config.rabbitmq
    if cfg is None:
        logger.warning("events.rabbitmq_adapter_skipped", reason="No rabbitmq config")
        return
    url = (
        cfg.url.get_secret_value()
        if hasattr(cfg.url, "get_secret_value")
        else str(cfg.url)
    )
    from quadkit.validation import SecretStr

    adapter_config = RabbitMQAdapterConfig(
        connection_string=SecretStr(url) if not isinstance(url, SecretStr) else url,
        exchange_name=cfg.exchange_name,
        prefetch_count=cfg.prefetch_count,
        queue_durable=cfg.durable,
    )
    adapter = RabbitMQAdapter(config=adapter_config)
    try:
        await adapter.connect()
    except Exception as exc:  # noqa: BLE001 — optional wiring: any connect failure logs and skips, never crashes startup
        logger.warning("events.rabbitmq_adapter_connect_failed", reason=str(exc))
        return

    # Outbound: EventBusProtocol → RabbitMQ
    async def _forward_to_rabbitmq(event: Any) -> None:
        try:
            await adapter.publish(event)
        except Exception as exc:  # noqa: BLE001 — forward failures must not break the bus
            logger.warning("events.rabbitmq_forward_failed", reason=str(exc))

    event_bus.subscribe_all(_forward_to_rabbitmq)

    # Register singleton so callers can resolve RabbitMQAdapter from container
    try:
        container.singleton(RabbitMQAdapter, adapter)
    except Exception:  # noqa: BLE001 — container may already be frozen
        pass  # container may already be frozen

    logger.info("events.rabbitmq_adapter_wired", exchange=cfg.exchange_name)
