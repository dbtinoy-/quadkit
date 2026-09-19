"""Configuration public exports for the app subsystem."""

from __future__ import annotations

from quadkit.app.config.discovery import ModuleDiscoveryConfig
from quadkit.app.config.models import AppConfig

__all__ = [
    "AppConfig",
    "ModuleDiscoveryConfig",
]
