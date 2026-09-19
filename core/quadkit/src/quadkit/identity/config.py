"""Configuration model for the core identity subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field

from quadkit.contracts.core.identity import IdStrategy
from quadkit.identity.constants import DEFAULT_ID_STRATEGY, DEFAULT_PREFIX_SEPARATOR


@dataclass(slots=True)
class IdentityConfig:
    """Identity subsystem configuration."""

    strategy: IdStrategy = DEFAULT_ID_STRATEGY
    prefix_map: dict[str, str] = field(default_factory=dict)
    prefix_separator: str = DEFAULT_PREFIX_SEPARATOR


__all__ = ["IdentityConfig"]
