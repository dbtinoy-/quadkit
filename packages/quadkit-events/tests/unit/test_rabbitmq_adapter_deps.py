import builtins

import pytest

from quadkit.events.adapters.rabbitmq import RabbitMQAdapter, RabbitMQAdapterConfig


@pytest.mark.asyncio
async def test_rabbitmq_connect_requires_aio_pika(monkeypatch):
    # Simulate import-time failure for aio_pika
    orig_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "aio_pika" or name.startswith("aio_pika."):
            raise ImportError("no module named aio_pika")
        return orig_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    adapter = RabbitMQAdapter(RabbitMQAdapterConfig())

    with pytest.raises(ImportError, match="aio-pika is required"):
        await adapter.connect()
