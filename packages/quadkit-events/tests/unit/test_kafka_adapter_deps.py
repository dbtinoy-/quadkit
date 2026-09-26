import sys
import types

import pytest

from quadkit.events.adapters.kafka import KafkaAdapter, KafkaAdapterConfig


@pytest.mark.asyncio
async def test_kafka_connect_requires_aiokafka(monkeypatch):
    # Ensure a fresh import environment for the adapter
    monkeypatch.setitem(sys.modules, "aiokafka", types.ModuleType("aiokafka"))

    adapter = KafkaAdapter(KafkaAdapterConfig())

    with pytest.raises(ImportError, match="aiokafka is required"):
        await adapter.connect()
