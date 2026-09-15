"""CompilerContext — shared mutable state threaded through compiler phases."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.di.module.dynamic import DynamicModule
    from quadkit.di.module.graph import ModuleNode, ProviderEntry


@dataclass
class CompilerContext:
    """Shared mutable state threaded through compiler phases.

    Created once per :meth:`ModuleCompiler.compile` call and passed to
    each :class:`CompilerPhase` in sequence.  Phases read and write this
    object to pass data forward through the pipeline.
    """

    root_modules: list[type | DynamicModule]
    """Module classes and DynamicModule instances passed to ``compile()``."""

    standalone_providers: list[Any]
    """Provider instances not belonging to any module."""

    nodes: dict[type, ModuleNode] = field(default_factory=dict)
    """Module nodes keyed by module class, populated by :class:`CollectPhase`."""

    dynamic_configs: dict[type, DynamicModule] = field(default_factory=dict)
    """DynamicModule descriptors keyed by module class."""

    visibility: dict[type, frozenset[type]] = field(default_factory=dict)
    """Per-module visibility sets, populated by :class:`VisibilityPhase`."""

    global_exports: frozenset[type] = field(default_factory=frozenset)
    """Union of all global-module exports, populated by :class:`VisibilityPhase`."""

    provider_order: list[ProviderEntry] = field(default_factory=list)
    """Ordered provider entries, populated by :class:`ProviderOrderingPhase`."""

    warnings: list[str] = field(default_factory=list)
    """Non-fatal issues collected across all phases."""
