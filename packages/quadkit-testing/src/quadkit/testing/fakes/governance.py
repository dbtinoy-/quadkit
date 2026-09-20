"""Fakes for resource unit tracking.

Currently exposes :class:`FakeResourceUnitTracker` for tests that exercise
non-LLM resource quota flows without spinning up the real persistence
backends or governance manager.

The fake mirrors the production :class:`ResourceUnitTracker`
public API and applies the same correctness rules (quota check before
increment for INSTANTANEOUS gauges, sliding/calendar/instantaneous routing)
so tests catch the same bugs the production tracker catches.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING

from quadkit.contracts.ai.governance.resource_unit import (
    ResourceExhaustedError,
    ResourceUsageSnapshot,
    ResourceWindowKind,
)
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.ai.governance.resource_unit import ResourceUnit


class FakeResourceUnitTracker:
    """In-memory ``ResourceUnitTracker`` for tests.

    Differences from the production tracker:

    * No persistence; everything is kept in dicts on the instance.
    * Sliding window counts are keyed by ``(tenant, unit)`` and incremented
      atomically on each consume — there is no wall-clock decay.  Tests
      that need decay should call :meth:`reset` between assertions.
    * Calendar buckets are keyed by ``(tenant, unit, period)`` where
      *period* is provided by the caller via :meth:`set_calendar_period`
      (default ``""``).  This avoids smuggling a clock into the fake.
    * Reconciliation behaves identically — :meth:`reconcile` overwrites
      the gauge for an INSTANTANEOUS unit.

    Args:
        units: Map of ``unit_name → ResourceUnit`` the fake knows about.
        get_quota: Callable that returns the limit for
            ``(tenant_id, unit_name)``.  Defaults to ``inf`` so every
            consume succeeds unless an explicit quota is provided.
    """

    def __init__(
        self,
        units: dict[str, ResourceUnit] | None = None,
        get_quota: Callable[[str, str], float] | None = None,
    ) -> None:
        self._units: dict[str, ResourceUnit] = dict(units or {})
        self._get_quota = get_quota or (lambda _t, _u: float("inf"))

        # gauges[(tenant, unit)] → current value
        self._gauges: dict[tuple[str, str], float] = defaultdict(float)
        # sliding[(tenant, unit)] → count
        self._sliding: dict[tuple[str, str], int] = defaultdict(int)
        # calendar[(tenant, unit, period)] → cumulative
        self._calendar: dict[tuple[str, str, str], float] = defaultdict(float)
        self._calendar_period: str = ""

        # Recorded calls — useful for assertions in tests
        self.consume_calls: list[tuple[str, str, float, str | None]] = []
        self.release_calls: list[tuple[str, str, float]] = []
        self.reconcile_calls: list[tuple[str, str, float]] = []

    def register_unit(self, unit: ResourceUnit) -> None:
        """Add a unit definition the fake recognises."""
        self._units[unit.name] = unit

    def set_calendar_period(self, period: str) -> None:
        """Set the period bucket for subsequent CALENDAR consume calls."""
        self._calendar_period = period

    def reset(self) -> None:
        """Clear all recorded usage and call history (test helper)."""
        self._gauges.clear()
        self._sliding.clear()
        self._calendar.clear()
        self.consume_calls.clear()
        self.release_calls.clear()
        self.reconcile_calls.clear()

    async def consume(
        self,
        tenant_id: str,
        unit_name: str,
        amount: float,
        actor_id: str | None = None,
    ) -> Result[ResourceUsageSnapshot, ResourceExhaustedError]:
        self.consume_calls.append((tenant_id, unit_name, amount, actor_id))

        unit = self._units.get(unit_name)
        if unit is None:
            return Err(
                ResourceExhaustedError(
                    tenant_id=tenant_id,
                    unit_name=unit_name,
                    limit=0,
                    current=0,
                    actor_id=actor_id,
                )
            )

        limit = self._get_quota(tenant_id, unit_name)
        if limit <= 0:
            return Err(
                ResourceExhaustedError(
                    tenant_id=tenant_id,
                    unit_name=unit_name,
                    limit=0,
                    current=0,
                    actor_id=actor_id,
                )
            )

        key = (tenant_id, unit_name)
        kind = unit.window_kind
        final_current = 0.0

        if kind == ResourceWindowKind.INSTANTANEOUS:
            current = self._gauges[key]
            if current + amount > limit:
                return Err(
                    ResourceExhaustedError(
                        tenant_id=tenant_id,
                        unit_name=unit_name,
                        limit=limit,
                        current=current,
                        actor_id=actor_id,
                    )
                )
            self._gauges[key] = current + amount
            final_current = self._gauges[key]
        elif kind == ResourceWindowKind.SLIDING:
            self._sliding[key] += 1
            final_current = float(self._sliding[key])
            if final_current > limit:
                return Err(
                    ResourceExhaustedError(
                        tenant_id=tenant_id,
                        unit_name=unit_name,
                        limit=limit,
                        current=final_current,
                        actor_id=actor_id,
                    )
                )
        elif kind == ResourceWindowKind.CALENDAR:
            cal_key = (tenant_id, unit_name, self._calendar_period)
            self._calendar[cal_key] += amount
            final_current = self._calendar[cal_key]
            if final_current > limit:
                return Err(
                    ResourceExhaustedError(
                        tenant_id=tenant_id,
                        unit_name=unit_name,
                        limit=limit,
                        current=final_current,
                        actor_id=actor_id,
                    )
                )

        return Ok(
            ResourceUsageSnapshot(
                tenant_id=tenant_id,
                unit_name=unit_name,
                current=float(final_current),
                limit=limit,
            )
        )

    async def release(self, tenant_id: str, unit_name: str, amount: float) -> None:
        self.release_calls.append((tenant_id, unit_name, amount))
        unit = self._units.get(unit_name)
        if unit is None or unit.window_kind != ResourceWindowKind.INSTANTANEOUS:
            return
        key = (tenant_id, unit_name)
        self._gauges[key] = max(self._gauges[key] - amount, 0.0)

    async def reconcile(
        self,
        tenant_id: str,
        unit_name: str,
        expected_amount: float,
    ) -> None:
        self.reconcile_calls.append((tenant_id, unit_name, expected_amount))
        unit = self._units.get(unit_name)
        if unit is None or unit.window_kind != ResourceWindowKind.INSTANTANEOUS:
            return
        self._gauges[(tenant_id, unit_name)] = max(expected_amount, 0.0)

    async def usage(self, tenant_id: str, unit_name: str) -> ResourceUsageSnapshot:
        limit = self._get_quota(tenant_id, unit_name)
        unit = self._units.get(unit_name)
        if unit is None:
            return ResourceUsageSnapshot(
                tenant_id=tenant_id,
                unit_name=unit_name,
                current=0.0,
                limit=limit,
            )
        key = (tenant_id, unit_name)
        current = 0.0
        if unit.window_kind == ResourceWindowKind.INSTANTANEOUS:
            current = self._gauges[key]
        elif unit.window_kind == ResourceWindowKind.SLIDING:
            current = float(self._sliding[key])
        elif unit.window_kind == ResourceWindowKind.CALENDAR:
            current = self._calendar[(tenant_id, unit_name, self._calendar_period)]
        return ResourceUsageSnapshot(
            tenant_id=tenant_id,
            unit_name=unit_name,
            current=float(current),
            limit=limit,
        )


__all__ = ["FakeResourceUnitTracker"]
