"""PluginsModule — opt-in entry point into the plugin engine."""

from __future__ import annotations

from pathlib import Path

from quadkit.di.module import DynamicModule, Module, module
from quadkit.plugins.engine import PluginEngineProvider

__all__ = ["PluginsModule"]


@module()
class PluginsModule(Module):
    """Module that activates entry-point plugin discovery at boot.

    Usage::

        # Option A — module auto-discovery in app config
        #   discovery:
        #     auto_discover: true      (scans ``quadkit.modules``)
        #
        # Option B — explicit
        from quadkit.plugins.module import PluginsModule

        app.add_module(PluginsModule.configure())
    """

    @classmethod
    def configure(
        cls,
        state_path: str | Path | None = None,
    ) -> DynamicModule:
        """Return a DynamicModule wiring ``PluginEngineProvider``.

        Args:
            state_path: Optional explicit plugin-state file path. Defaults
                to the state module's env-var / default resolution.

        Returns:
            A DynamicModule exporting the plugin engine provider.
        """
        return DynamicModule(
            module=cls,
            providers=[PluginEngineProvider(state_path=state_path)],
            exports=[],
        )
