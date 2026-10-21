"""The event bus has a shutdown path, and explicit provider config survives boot.

Both gaps were found by wiring the bus into a real application:

* ``publish()`` returns once the event is queued; a background drain task
  delivers it. Nothing stopped those tasks, so ``EventsProvider.shutdown()``
  left them polling, and an event accepted just before shutdown was lost.
* ``EventsProvider(config=...)`` never set ``_config_from_factory``, so the
  orchestrator replaced the explicit config with the ``events:`` yaml
  section — or, with no such section, with ``EventsConfig()`` defaults.
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from quadkit.contracts.domain import DomainEvent
from quadkit.events.buses import EventBusImpl
from quadkit.events.config import EventBusConfig, EventsConfig
from quadkit.events.di.provider import EventsProvider


class _Happened(DomainEvent):
    pass


async def test_close_delivers_what_was_accepted_then_stops_the_drain_tasks() -> None:
    bus = EventBusImpl(config=EventBusConfig(retry_failed_handlers=False))
    seen: list[int] = []
    release = asyncio.Event()

    async def handler(event: _Happened) -> None:
        await release.wait()
        seen.append(1)

    bus.subscribe(_Happened, handler)
    await bus.publish(_Happened())
    await bus.publish(_Happened())
    assert bus._background_tasks, "a drain task runs behind the channel"

    closer = asyncio.create_task(bus.close(timeout=5))
    await asyncio.sleep(0)
    release.set()
    await closer

    assert seen == [1, 1], "events accepted before close() are still handled"
    assert all(task.done() for task in bus._background_tasks)


async def test_close_is_idempotent_and_refuses_new_events() -> None:
    bus = EventBusImpl()
    bus.subscribe(_Happened, lambda event: None)
    await bus.close()
    await bus.close()

    result = await bus.publish(_Happened())
    assert result.is_err()
    assert "closed" in str(result.unwrap_err())
    assert not any(not task.done() for task in bus._background_tasks), "no drain task was started after close"


async def test_close_cancels_a_handler_that_outlives_the_timeout() -> None:
    bus = EventBusImpl(config=EventBusConfig(retry_failed_handlers=False, handler_timeout_seconds=60))
    started = asyncio.Event()

    async def stuck(event: _Happened) -> None:
        started.set()
        await asyncio.sleep(3600)

    bus.subscribe(_Happened, stuck)
    await bus.publish(_Happened())
    await started.wait()

    await bus.close(timeout=0.05)
    assert all(task.done() for task in bus._background_tasks)


async def test_close_does_not_spend_the_timeout_on_a_foreign_drain_task() -> None:
    """A drain task started on another loop must not block shutdown.

    ``_ensure_channel_for`` starts the drain task on whichever loop first
    publishes, so an app driven through a test client — lifespan in the
    client's portal loop, publishing from the test's own loop — ends up with a
    drain task the closing loop cannot observe. ``asyncio.wait`` learns
    completion through a done-callback scheduled on the *task's* loop, so it
    stayed blocked for the whole ``timeout``; during application shutdown that
    timeout is the entire shutdown budget, and the shutdown failed.
    """
    bus = EventBusImpl(config=EventBusConfig(retry_failed_handlers=False))

    async def blocking(event: _Happened) -> None:
        await asyncio.sleep(3600)

    bus.subscribe(_Happened, blocking)

    # Publish from a loop running in another thread, so the drain task is
    # created on that loop rather than on this one.
    foreign_loop = asyncio.new_event_loop()
    worker = threading.Thread(target=foreign_loop.run_forever, daemon=True)
    worker.start()
    try:
        asyncio.run_coroutine_threadsafe(bus.publish(_Happened()), foreign_loop).result(timeout=5)
        foreign = [task for task in bus._background_tasks if task.get_loop() is foreign_loop]
        assert foreign, "the drain task belongs to the loop that published, not this one"
        assert all(task.get_loop() is not asyncio.get_running_loop() for task in foreign)

        started = time.monotonic()
        await bus.close(timeout=10)
        elapsed = time.monotonic() - started
    finally:
        foreign_loop.call_soon_threadsafe(foreign_loop.stop)
        worker.join(timeout=5)
        foreign_loop.close()

    assert elapsed < 2, f"close() spent {elapsed:.1f}s of its timeout on a task it cannot observe"


async def test_provider_shutdown_closes_the_event_bus() -> None:
    provider = EventsProvider(config=EventsConfig())
    _, buses, _ = provider._ensure_composed()
    await buses.setup()
    bus = buses.event_bus
    bus.subscribe(_Happened, lambda event: None)
    await bus.publish(_Happened())

    await provider.shutdown()

    assert bus._closed is True
    assert all(task.done() for task in bus._background_tasks)


def test_explicit_config_is_marked_authoritative() -> None:
    explicit = EventsProvider(config=EventsConfig(event_bus=EventBusConfig(handler_timeout_seconds=5)))
    assert explicit._config_from_factory is True
    assert explicit.config is not None
    assert explicit.config.event_bus.handler_timeout_seconds == 5

    injected = EventsProvider()
    assert injected._config_from_factory is False, "zero-config construction still takes the yaml section"


@pytest.mark.parametrize("as_dict", [True, False])
def test_dict_config_counts_as_explicit(as_dict: bool) -> None:
    config = {"event_bus": {"handler_timeout_seconds": 7}} if as_dict else EventsConfig()
    provider = EventsProvider(config=config)
    assert provider._config_from_factory is True


async def test_flush_waits_for_a_handler_the_drain_task_has_not_resumed_for() -> None:
    """``flush()`` after ``publish()`` means the handler ran, on every tick.

    Regression for a one-tick gap in ``BoundedChannel`` where the item had
    left the queue but the drain task had not yet counted it in flight.
    """
    bus = EventBusImpl(config=EventBusConfig(retry_failed_handlers=False))
    handled: list[int] = []

    async def handler(event: _Happened) -> None:
        handled.append(1)

    bus.subscribe(_Happened, handler)
    try:
        for round_no in range(1, 6):
            await bus.publish(_Happened())
            await bus.flush()
            assert len(handled) == round_no, f"flush returned before handler on round {round_no}"
    finally:
        await bus.close()
