"""Log sampling configuration for the logging subsystem."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.domain import DomainModel
from quadkit.validation import Field, model_validator


@dataclass(init=False)
class SamplingConfig(DomainModel):
    """Log sampling configuration for rate-limiting high-volume events.

    Attributes:
        enabled: Whether log sampling is enabled.
        default_rate: Sampling rate (0.0 to 1.0). For example, 0.1 means 10%
            of log events are kept.
        rules: Per-event sampling rate overrides keyed by event name. For
            example, ``{"request_received": 0.01}`` keeps 1% of those events.
    """

    enabled: bool = Field(default=False)
    default_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    rules: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_rate(self) -> SamplingConfig:
        """Clamp the rate to a valid range if somehow outside bounds."""
        self.default_rate = max(0.0, min(1.0, self.default_rate))
        return self


__all__ = ["SamplingConfig"]
