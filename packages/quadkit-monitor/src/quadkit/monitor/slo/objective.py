"""SLO (Service Level Objective) data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from quadkit.contracts.monitor.projection_tier import ProjectionTier


@dataclass
class SLO:
    """Defines an acceptable performance target for a monitored metric.

    An SLO specifies the maximum tolerable value for a percentile of a
    metric (e.g. ``p99 latency < 200 ms``) and the error-budget burn-rate
    threshold above which an alert should be raised.

    Attributes:
        name: Unique name for this SLO (e.g. ``"api.p99_latency"``).
        metric: Name of the metric to evaluate (e.g.
            ``"http.request.duration"``).
        percentile: Target percentile expressed as a fraction between
            0.0 and 1.0 (e.g. ``0.99`` for p99).
        threshold_ms: Maximum acceptable measured value in milliseconds.
        window: Measurement window for rolling evaluation.
        burn_rate_threshold: Fire an alert when the measured/threshold ratio
            equals or exceeds this value.  A value of ``1.0`` means "alert
            the moment the threshold is exceeded".
        description: Optional human-readable description of the SLO.
        tier: Alert routing tier. Defaults to P1_BUSINESS_HOURS.
        owner: Team or spec ID responsible for this SLO.
        runbook_url: URL pointing to the runbook for this SLO.
    """

    name: str
    metric: str
    percentile: float
    threshold_ms: float
    window: timedelta = field(default_factory=lambda: timedelta(hours=1))
    burn_rate_threshold: float = 1.0
    description: str = ""
    tier: ProjectionTier = ProjectionTier.P1_BUSINESS_HOURS
    owner: str = ""
    runbook_url: str | None = None


@dataclass
class SLOViolation:
    """Represents a detected SLO threshold breach.

    Attributes:
        slo: The SLO that was violated.
        measured_value: The percentile value that exceeded the threshold (ms).
        burn_rate: ratio of *measured_value* to ``slo.threshold_ms`` at the
            time of detection.
        detected_at: UTC timestamp when the violation was detected.
        message: Human-readable summary, auto-generated when empty.
    """

    slo: SLO
    measured_value: float
    burn_rate: float
    detected_at: datetime
    message: str = ""

    def __post_init__(self) -> None:
        if not self.message:
            pct = int(self.slo.percentile * 100)
            self.message = (
                f"SLO '{self.slo.name}' violated: p{pct} = {self.measured_value:.1f}ms"
                f" > threshold {self.slo.threshold_ms:.1f}ms"
                f" (burn rate: {self.burn_rate:.2f}x)"
            )


__all__ = ["SLO", "SLOViolation"]
