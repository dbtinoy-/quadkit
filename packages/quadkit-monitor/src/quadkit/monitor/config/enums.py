"""Monitor configuration enums."""

from __future__ import annotations

from enum import StrEnum


class BackendType(StrEnum):
    """Supported monitoring backend types."""

    OPENTELEMETRY = "opentelemetry"
    PROMETHEUS = "prometheus"
    MEMORY = "memory"


class SamplerType(StrEnum):
    """Supported tracing sampler types."""

    ALWAYS_ON = "always_on"
    ALWAYS_OFF = "always_off"
    PROBABILITY = "probability"
    RATE_LIMITING = "rate_limiting"
    PARENT_BASED = "parent_based"


__all__ = [
    "BackendType",
    "SamplerType",
]
