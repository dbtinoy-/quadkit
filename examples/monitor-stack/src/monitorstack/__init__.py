"""Monitor stack demo — health checks, metrics, and tracing.

Convention followed: **Package exports** — ``__init__.py`` re-exports
the public API surface without defining logic.

Exports:

- ``create_app`` — composition root for the application
- ``MonitorStackConfig`` — demo configuration model
- ``MonitorStackProvider`` — DI provider for monitoring services
"""

from __future__ import annotations

from monitorstack.app import create_app
from monitorstack.config import MonitorStackConfig
from monitorstack.di.provider import MonitorStackProvider

__all__ = [
    "MonitorStackConfig",
    "MonitorStackProvider",
    "create_app",
]
