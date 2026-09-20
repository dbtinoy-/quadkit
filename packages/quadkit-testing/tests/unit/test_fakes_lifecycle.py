"""Governance tracking and unit-of-work lifecycles for the fakes cluster."""

from __future__ import annotations

from typing import Any

import pytest

# ---------------------------------------------------------------------------
# FakeResourceUnitTracker (governance)
# ---------------------------------------------------------------------------


def _unit(name: str, kind: Any) -> Any:
    from quadkit.contracts.ai.governance.resource_unit import ResourceUnit

    return ResourceUnit(name=name, unit_kind="test", window_kind=kind)


async def test_governance_tracker_instantaneous() -> None:
    from quadkit.contracts.ai.governance.resource_unit import ResourceWindowKind
    from quadkit.testing.fakes.governance import FakeResourceUnitTracker

    tracker = FakeResourceUnitTracker(
        units={"mem": _unit("mem", ResourceWindowKind.INSTANTANEOUS)},
        get_quota=lambda _t, _u: 10.0,
    )

    ok = await tracker.consume("t1", "mem", 4.0)
    assert ok.is_ok()
    assert ok.unwrap().current == 4.0

    err = await tracker.consume("t1", "mem", 7.0)
    assert err.is_err()

    await tracker.release("t1", "mem", 4.0)
    snap = await tracker.usage("t1", "mem")
    assert snap.current == 0.0


async def test_governance_tracker_sliding_calendar_and_errors() -> None:
    from quadkit.contracts.ai.governance.resource_unit import ResourceWindowKind
    from quadkit.testing.fakes.governance import FakeResourceUnitTracker

    tracker = FakeResourceUnitTracker(
        units={
            "req": _unit("req", ResourceWindowKind.SLIDING),
            "quota": _unit("quota", ResourceWindowKind.CALENDAR),
        },
        get_quota=lambda _t, unit: 2.0 if unit == "req" else 100.0,
    )

    ok1 = await tracker.consume("t1", "req", 1)
    assert ok1.is_ok() and ok1.unwrap().current == 1.0
    ok2 = await tracker.consume("t1", "req", 1)
    assert ok2.is_ok() and ok2.unwrap().current == 2.0
    over = await tracker.consume("t1", "req", 1)
    assert over.is_err()

    tracker.set_calendar_period("2026-09")
    cal = await tracker.consume("t1", "quota", 25.5)
    assert cal.is_ok() and cal.unwrap().current == 25.5
    cal2 = await tracker.consume("t1", "quota", 25.5)
    assert cal2.unwrap().current == 51.0

    # unknown unit and zero quota
    unknown = await tracker.consume("t1", "ghost", 1)
    assert unknown.is_err()

    zero_quota = FakeResourceUnitTracker(
        units={"z": _unit("z", ResourceWindowKind.SLIDING)},
        get_quota=lambda _t, _u: 0.0,
    )
    assert (await zero_quota.consume("t1", "z", 1)).is_err()

    # reconciliation overwrites the gauge
    recon = FakeResourceUnitTracker(
        units={"mem": _unit("mem", ResourceWindowKind.INSTANTANEOUS)},
    )
    await recon.consume("t1", "mem", 3.0)
    await recon.reconcile("t1", "mem", 1.5)
    assert (await recon.usage("t1", "mem")).current == 1.5

    assert len(tracker.consume_calls) == 6
    tracker.reset()
    assert tracker.consume_calls == []
    assert (await tracker.usage("t1", "req")).current == 0.0


# ---------------------------------------------------------------------------
# FakeUnitOfWork (lifecycle)
# ---------------------------------------------------------------------------


async def test_fake_unit_of_work_commit_and_rollback() -> None:
    from quadkit.testing.fakes.events import FakeEventBus
    from quadkit.testing.fakes.lifecycle import FakeUnitOfWork

    bus = FakeEventBus()
    async with FakeUnitOfWork(event_bus=bus) as uow:
        uow.register_new("entity-1")
        uow.register_dirty("entity-2")
        uow.register_deleted("entity-3")
        uow.register_event("event-1")
        assert uow.collect_events() == ["event-1"]
        assert uow.committed is False
    # exited without explicit commit -> auto-committed
    assert uow.committed is True
    assert uow.rolled_back is False
    assert len(bus.published) == 1

    async def boom() -> None:
        async with FakeUnitOfWork() as uow2:
            uow2.register_new("x")
            raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        await boom()
    # rolled back on exception — inspect via a fresh instance
    uow3 = FakeUnitOfWork()
    try:
        async with uow3:
            uow3.register_new("y")
            raise ValueError("x")
    except ValueError:
        pass
    assert uow3.rolled_back is True
    assert uow3.new == []

    # explicit rollback
    uow4 = FakeUnitOfWork()
    uow4.register_new("z")
    await uow4.rollback()
    assert uow4.rolled_back is True
    assert uow4.new == []
