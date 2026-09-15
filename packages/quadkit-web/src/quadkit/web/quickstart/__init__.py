"""Quick-start module for single-file Quadkit web applications."""

from __future__ import annotations

from quadkit.web.quickstart.core import (
    _QUICKSTART_REGISTRY,
    _QUICKSTART_ROUTE_REGISTRY,
    _PendingRoute,
    _QuickstartApp,
    _reset_quickstart_registry,
    app,
    injectable,
    singleton,
)

__all__ = [
    "_QUICKSTART_REGISTRY",
    "_QUICKSTART_ROUTE_REGISTRY",
    "_PendingRoute",
    "_QuickstartApp",
    "_reset_quickstart_registry",
    "app",
    "injectable",
    "singleton",
]
