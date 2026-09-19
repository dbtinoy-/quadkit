"""Entry-point plugin discovery and boot-time enable/disable state."""

from __future__ import annotations

from quadkit.plugins.discovery import discover_plugins, discover_providers
from quadkit.plugins.engine import PluginEngineProvider
from quadkit.plugins.module import PluginsModule
from quadkit.plugins.state import load_disabled, save_disabled, update_disabled

__all__ = [
    "PluginEngineProvider",
    "PluginsModule",
    "discover_plugins",
    "discover_providers",
    "load_disabled",
    "save_disabled",
    "update_disabled",
]
