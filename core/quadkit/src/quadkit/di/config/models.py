"""Configuration models for the DI subsystem.

Contains :class:`DiConfig`, which controls resolution depth, validation,
and strictness of the dependency injection container.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.di.constants import DEFAULT_MAX_RESOLUTION_DEPTH


@dataclass
class DiConfig:
    """Dependency injection container, providers, and resolution engine configuration."""

    debug_resolution: bool = False
    # consumed by: DIResolverProtocol — verbose per-step resolution logging
    max_resolution_depth: int = DEFAULT_MAX_RESOLUTION_DEPTH
    # consumed by: DIResolverProtocol cycle detection
    validate_on_register: bool = True
    # consumed by: Container.singleton / Container.transient guard checks
    strict_mode: bool = False
    # consumed by: Container — raise on unknown type resolution instead of returning None
    type_hint_cache_size: int = 2048
    # consumed by: TypeHintResolverImpl — LRU cache size for resolved type-hint signatures


__all__ = ["DiConfig"]
