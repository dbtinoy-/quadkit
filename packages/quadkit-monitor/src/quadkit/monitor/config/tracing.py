"""Tracing configuration."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.config import BaseConfig
from quadkit.monitor import constants as monitor_const
from quadkit.monitor.config.enums import SamplerType
from quadkit.validation import Field, field_validator


@dataclass(init=False)
class TracingConfig(BaseConfig):
    """Configuration for distributed tracing.

    Attributes:
        enabled: Whether tracing is enabled.
        service_name: Name of the service for traces.
        sampler_type: Type of sampling strategy.
        sample_rate: Sampling rate (0.0 to 1.0) for probability sampler.
        max_traces_per_second: Max traces/sec for rate limiting sampler.
        propagation_formats: Trace context propagation formats.
        max_attributes: Maximum attributes per span.
        max_events: Maximum events per span.
        max_links: Maximum links per span.
    """

    enabled: bool = Field(True, description="Enable tracing")
    service_name: str = Field(
        monitor_const.DEFAULT_SERVICE_NAME, description="Service name for traces"
    )
    sampler_type: SamplerType = Field(
        SamplerType.ALWAYS_ON,
        description="Tracing sampler type",
    )
    sample_rate: float = Field(
        1.0,
        ge=0.0,
        le=1.0,
        description="Sample rate (0.0 to 1.0)",
    )
    max_traces_per_second: int = Field(
        100,
        ge=0,
        description="Max traces to sample per second",
    )
    propagation_formats: list[str] = Field(
        default_factory=lambda: ["tracecontext", "baggage"],
        description="Propagation format list",
    )
    max_attributes: int = Field(128, ge=1, description="Max attributes per span")
    max_events: int = Field(128, ge=1, description="Max events per span")
    max_links: int = Field(128, ge=1, description="Max links per span")
    max_spans: int = Field(
        monitor_const.DEFAULT_MAX_SPANS,
        ge=1,
        description="Max number of spans to keep in memory",
    )

    @field_validator("sample_rate")
    @classmethod
    def validate_sample_rate(cls, v: float) -> float:
        """Validate sample rate is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("sample_rate must be between 0.0 and 1.0")
        return v


__all__ = [
    "TracingConfig",
]
