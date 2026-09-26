"""Shared attribute surface for MonitorProvider mixins.

Declared once so every phase mixin (and mypy) sees the same attributes;
``MonitorProvider.__init__`` performs the concrete assignments.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


class _MonitorAttrsMixin:
    """Attribute contract shared by all MonitorProvider mixins."""

    backend: Any
    metrics_collector: Any
    metrics_exporter: Any
    tracer: Any
    trace_provider: Any
    _config: Any
    _requested_config: Any
    _config_from_factory: bool
    _hook_handlers: Any
    _hook_registry: Any
    _metrics_exporter_registry: Any
    _tracing_exporter_registry: Any
    _health_checker_registry: Any
    _slo_monitor: Any
    _slo_worker: Any
    _digest_worker: Any
    _error_tracker: Any
    _error_hook: Any
    _register_hook_subscriptions: Callable[..., Any]
    _compose_tracing: Callable[..., Any]
    _resolve_slo_monitor: Callable[..., Any]
    _resolve_slo_worker: Callable[..., Any]
