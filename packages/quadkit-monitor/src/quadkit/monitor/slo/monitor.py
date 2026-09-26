"""SLO monitor — tracks compliance and detects budget violations."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
import math
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger
from quadkit.monitor.slo.objective import SLO, SLOViolation

if TYPE_CHECKING:
    from quadkit.contracts.observability.metrics import AlertDispatcherProtocol

logger = get_logger(__name__)


class SLOMonitor:
    """Tracks SLO compliance and fires alerts on error-budget exhaustion.

    Records metric samples in memory, then evaluates each registered SLO
    when :meth:`evaluate` is called.  Violations are returned as a list of
    :class:`SLOViolation` objects and also emitted as structured log warnings.

    When *alert_dispatcher* is provided, :meth:`evaluate_and_dispatch`
    sends each violation through the dispatcher with tier-aware context and
    respects *suppression_window_seconds* to avoid alert storms.

    Example::

        from datetime import timedelta
        from quadkit.monitor.slo import SLO, SLOMonitor

        monitor = SLOMonitor()
        monitor.register(SLO(
            name="api.p99_latency",
            metric="http.request.duration",
            percentile=0.99,
            threshold_ms=200.0,
            window=timedelta(hours=1),
        ))

        monitor.record_sample("http.request.duration", 150.0)
        monitor.record_sample("http.request.duration", 350.0)

        violations = await monitor.evaluate()
    """

    def __init__(
        self,
        max_samples_per_metric: int = 10_000,
        alert_dispatcher: AlertDispatcherProtocol | None = None,
        suppression_window_seconds: int = 300,
    ) -> None:
        self._slos: dict[str, SLO] = {}
        self._max_samples = max_samples_per_metric
        self._samples: dict[str, deque[tuple[datetime, float]]] = {}
        self._alert_dispatcher = alert_dispatcher
        self._suppression_window = suppression_window_seconds
        self._last_dispatched: dict[str, datetime] = {}

    def register(self, slo: SLO) -> None:
        """Register an SLO for monitoring.

        Args:
            slo: The :class:`SLO` to track.

        Raises:
            ValueError: If an SLO with the same name is already registered.
        """
        if slo.name in self._slos:
            raise ValueError(f"SLO '{slo.name}' is already registered")
        self._slos[slo.name] = slo
        logger.info(
            "slo_registered",
            name=slo.name,
            metric=slo.metric,
            percentile=slo.percentile,
            threshold_ms=slo.threshold_ms,
        )

    def record_sample(
        self,
        metric: str,
        value_ms: float,
        *,
        at: datetime | None = None,
    ) -> None:
        """Record a measurement sample for a metric.

        Samples carry a UTC timestamp so :meth:`evaluate` can restrict
        each SLO to its configured rolling ``window``.

        Args:
            metric: The metric name (matches registered SLO ``metric`` fields).
            value_ms: The measurement value in milliseconds.
            at: Optional explicit sample timestamp (UTC).  Defaults to
                "now"; accept an explicit value when replaying recorded
                data or in tests.
        """
        if metric not in self._samples:
            self._samples[metric] = deque(maxlen=self._max_samples)
        timestamp = at.astimezone(UTC) if at is not None else datetime.now(tz=UTC)
        self._samples[metric].append((timestamp, value_ms))

    def _compute_percentile(self, values: list[float], percentile: float) -> float:
        """Compute a percentile value from a list of samples.

        Uses the nearest-rank method: the p-th percentile is the value at
        rank ``ceil(p * N)`` (1-based) in the sorted samples.

        Args:
            values: Measurement values (any order).
            percentile: Target percentile (0.0 – 1.0).

        Returns:
            The computed percentile value.
        """
        if not values:
            return 0.0
        ordered = sorted(values)
        rank = max(1, math.ceil(percentile * len(ordered)))
        return ordered[rank - 1]

    async def evaluate(self) -> list[SLOViolation]:
        """Evaluate all registered SLOs against recorded samples.

        Returns:
            A list of :class:`SLOViolation` instances for every SLO that
            is in breach. Returns an empty list when all SLOs are within
            bounds or when no samples have been recorded yet.
        """
        violations: list[SLOViolation] = []
        now = datetime.now(tz=UTC)

        for slo in self._slos.values():
            samples = self._samples.get(slo.metric)
            if not samples:
                continue

            # Rolling window: only samples inside slo.window count.
            cutoff = now - slo.window
            windowed = [value for ts, value in samples if ts >= cutoff]
            if not windowed:
                continue

            measured = self._compute_percentile(windowed, slo.percentile)
            if measured > slo.threshold_ms:
                burn_rate = measured / slo.threshold_ms
                if burn_rate >= slo.burn_rate_threshold:
                    violation = SLOViolation(
                        slo=slo,
                        measured_value=measured,
                        burn_rate=burn_rate,
                        detected_at=now,
                    )
                    violations.append(violation)
                    logger.warning(
                        "slo_violation",
                        name=slo.name,
                        metric=slo.metric,
                        measured_ms=measured,
                        threshold_ms=slo.threshold_ms,
                        burn_rate=burn_rate,
                    )

        return violations

    async def evaluate_and_dispatch(self) -> list[SLOViolation]:
        """Evaluate all SLOs and dispatch violations through the alert dispatcher.

        Each violation is routed through ``self._alert_dispatcher`` with
        tier-aware context when available.  Duplicate alerts for the same
        SLO are suppressed within *suppression_window_seconds*.

        Returns:
            The full list of violations (same as :meth:`evaluate`).
        """
        violations = await self.evaluate()
        if self._alert_dispatcher is None:
            return violations

        now = datetime.now(tz=UTC)
        for v in violations:
            if not self._should_dispatch(v.slo.name, now):
                continue
            context: dict[str, Any] = {
                "tier": v.slo.tier.value,
                "slo_name": v.slo.name,
                "owner": v.slo.owner,
                "runbook_url": v.slo.runbook_url,
                "burn_rate": v.burn_rate,
            }
            await self._alert_dispatcher.send_metric_alert(
                metric_name=v.slo.metric,
                current_value=v.measured_value,
                threshold=v.slo.threshold_ms,
                context=context,
            )
            self._last_dispatched[v.slo.name] = now
        return violations

    def _should_dispatch(self, slo_name: str, now: datetime) -> bool:
        """Check if enough time has passed since the last dispatch for *slo_name*."""
        last = self._last_dispatched.get(slo_name)
        if last is None:
            return True
        elapsed = (now - last).total_seconds()
        return elapsed >= self._suppression_window

    @property
    def registered_slos(self) -> dict[str, SLO]:
        """Return registered SLOs keyed by name."""
        return dict(self._slos)

    def clear_samples(self, metric: str | None = None) -> None:
        """Remove recorded samples.

        Args:
            metric: If given, only clears samples for that metric.
                When ``None``, clears all recorded samples.
        """
        if metric is not None:
            self._samples.pop(metric, None)
        else:
            self._samples.clear()


__all__ = ["SLOMonitor"]
