"""apply_overrides and ContainerFactory.create_test_container."""

from __future__ import annotations

from typing import Any

import pytest
from quadkit.contracts.core.config import ConfigProtocol
from quadkit.testing.fakes import (
    FakeConfig,
)
from quadkit.testing.fixtures.containers import (
    ContainerFactory,
    apply_overrides,
)

# ---------------------------------------------------------------------------
# apply_overrides
# ---------------------------------------------------------------------------


def test_apply_overrides_singleton_path() -> None:
    from quadkit.di.container import Container

    container = Container()
    impl = FakeConfig({"a.b": 1})
    apply_overrides(container, {ConfigProtocol: impl})
    instance = container.resolve_sync(ConfigProtocol)
    assert instance is impl


def test_apply_overrides_transient_path() -> None:
    class TransientOnly:
        def __init__(self) -> None:
            self.registered: list[tuple] = []

        def transient(self, interface: type, factory: Any) -> None:
            self.registered.append((interface, factory))

    container = TransientOnly()
    impl = object()
    apply_overrides(container, {ConfigProtocol: impl})
    assert len(container.registered) == 1
    assert container.registered[0][0] is ConfigProtocol
    assert container.registered[0][1]() is impl


def test_apply_overrides_no_api_raises() -> None:
    class NoApi:
        pass

    with pytest.raises(RuntimeError, match="does not support known registration"):
        apply_overrides(NoApi(), {ConfigProtocol: object()})


# ---------------------------------------------------------------------------
# ContainerFactory.create_test_container + memory implementations
# ---------------------------------------------------------------------------


async def test_create_test_container_registers_protocols() -> None:
    import quadkit.contracts as oc

    container = ContainerFactory().create_test_container()

    state_store = await container.resolve(oc.StateStoreProtocol)
    await state_store.set("k", "v")
    assert await state_store.get("k") == "v"

    secret_store = await container.resolve(oc.SecretStoreProtocol)
    secret_store.set_secret("s", "v")
    assert secret_store.get_secret("s") == "v"

    lock = await container.resolve(oc.AsyncLockProtocol)
    assert await lock.acquire() is True
    lock.release()
    assert lock.locked() is False

    # Provider protocol mocks registered by the harness convention.
    from quadkit.contracts import (
        AuthProviderProtocol,
        CacheProviderProtocol,
        DatabaseProviderProtocol,
        TaskProviderProtocol,
    )

    db = await container.resolve(DatabaseProviderProtocol)
    assert await db.is_connected() is True
    cache = await container.resolve(CacheProviderProtocol)
    assert cache is not None
    auth = await container.resolve(AuthProviderProtocol)
    assert await auth.verify_token("t") is False
    task = await container.resolve(TaskProviderProtocol)
    assert task.get_worker_stats() == {}


def test_memory_lock_store() -> None:
    factory = ContainerFactory()
    lock = factory._create_memory_lock_store()

    assert lock.locked() is False
    import asyncio

    assert asyncio.run(lock.acquire()) is True
    assert lock.locked() is True
    # Non-blocking re-acquire while held → False.
    assert asyncio.run(lock.acquire()) is False
    lock.release()
    assert lock.locked() is False
    with pytest.raises(RuntimeError, match="Lock is not held"):
        lock.release()

    async def _ctx() -> bool:
        async with lock as entered:
            assert entered is lock
            assert lock.locked() is True
        return lock.locked() is False

    assert asyncio.run(_ctx())


async def test_memory_pubsub() -> None:
    pubsub = ContainerFactory()._create_memory_pubsub()
    received: list[Any] = []

    async def handler(message: Any) -> None:
        received.append(message)

    await pubsub.publish("ch", "before")  # no subscribers → no-op
    assert received == []
    await pubsub.subscribe("ch", handler)
    await pubsub.subscribe("ch", handler)
    await pubsub.publish("ch", "hello")
    assert received == ["hello", "hello"]

    # unsubscribe removes one registered instance of the callback.
    await pubsub.unsubscribe("ch", handler)
    await pubsub.publish("ch", "after")
    assert received == ["hello", "hello", "after"]
    await pubsub.unsubscribe("ch", handler)
    await pubsub.publish("ch", "gone")
    assert received == ["hello", "hello", "after"]
    # Unsubscribe from unknown channel → no-op.
    await pubsub.unsubscribe("unknown", handler)


def test_memory_secret_store() -> None:
    store = ContainerFactory()._create_memory_secret_store()
    assert store.has_secret("s") is False
    store.set_secret("s", "v1")
    assert store.get_secret("s") == "v1"
    assert store.has_secret("s") is True
    store.set_secret("s", "v2")
    assert store.get_secret("s") == "v2"
    store.delete_secret("s")
    assert store.has_secret("s") is False
    store.delete_secret("s")  # idempotent

    from quadkit.contracts.exceptions.components import SecretNotFoundError

    with pytest.raises(SecretNotFoundError, match="Secret 'missing' not found"):
        store.get_secret("missing")


async def test_memory_state_store_basic() -> None:
    store = ContainerFactory()._create_memory_state_store()
    assert await store.get("k") is None
    assert await store.exists("k") is False
    assert await store.delete("k") is False

    await store.set("k", "v")
    assert await store.get("k") == "v"
    assert await store.exists("k") is True
    assert await store.ttl("k") == -1  # no expiry

    await store.set("k2", "v2", ttl=100)
    assert await store.ttl("k2") >= 99
    assert await store.expire("k2", 50) is True
    assert 49 <= await store.ttl("k2") <= 50
    assert await store.expire("nope", 5) is False

    assert await store.delete("k") is True
    assert await store.get("k") is None

    # set without ttl clears a previous expiry.
    await store.set("k3", "v3", ttl=100)
    await store.set("k3", "v3b")
    assert await store.ttl("k3") == -1


async def test_memory_state_store_expiry() -> None:
    import asyncio

    store = ContainerFactory()._create_memory_state_store()
    await store.set("k", "v", ttl=1)
    assert await store.get("k") == "v"

    await asyncio.sleep(1.05)
    assert await store.get("k") is None  # expired → deleted
    assert await store.exists("k") is False
    assert await store.ttl("k") == -2

    # get_many / set_many
    await store.set_many({"a": 1, "b": 2}, ttl=60)
    many = await store.get_many(["a", "b", "missing"])
    assert many == {"a": 1, "b": 2}


# ---------------------------------------------------------------------------
