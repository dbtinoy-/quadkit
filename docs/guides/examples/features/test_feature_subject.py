"""Feature tour: Subjects — hot multicast with replay.

A `Subject` fans published items out to every current subscriber, and with
`replay=N` a late subscriber starts with a snapshot of the newest N items
before continuing live. `complete()` unwinds every iterator cleanly —
no polling, no sagas.
"""

import asyncio

import pytest

from quadkit.reactive import Subject


@pytest.mark.asyncio
async def test_multicast_reaches_all_subscribers() -> None:
    subject: Subject[str] = Subject()

    async def collect(name: str, count: int) -> list[str]:
        items: list[str] = []
        async for item in subject:
            items.append(f"{name}:{item}")
            if len(items) == count:
                break
        return items

    first = asyncio.create_task(collect("a", 2))
    second = asyncio.create_task(collect("b", 2))
    await asyncio.sleep(0)  # let both subscribe

    await subject.publish("boot")
    await subject.publish("ready")

    assert await first == ["a:boot", "a:ready"]
    assert await second == ["b:boot", "b:ready"]
    assert subject.subscriber_count == 0  # both iterators broke out


@pytest.mark.asyncio
async def test_replay_warms_late_subscribers() -> None:
    subject: Subject[int] = Subject(replay=2)

    await subject.publish(1)
    await subject.publish(2)
    await subject.publish(3)

    assert subject.replay_snapshot() == [2, 3]  # newest two retained

    late: list[int] = []

    async def collect_late() -> None:
        async for item in subject:
            late.append(item)
            if len(late) == 3:
                break

    task = asyncio.create_task(collect_late())
    await asyncio.sleep(0)  # subscriber attaches; replay drained
    await subject.publish(4)  # one more live item

    await task
    assert late == [2, 3, 4]  # replay history, then live

    await subject.complete()
    # A completed subject yields nothing further to new consumers — but the
    # replay window itself is still readable (newest two of all published).
    drained = [item async for item in subject]
    assert drained == [3, 4]
