"""CLI tooling module for dependency injection."""

from __future__ import annotations

from typing import Any

from quadkit.cli.protocols import CLIApplicationProtocol
from quadkit.di.module import DynamicModule, Module, module


@module()
class CLIModule(Module):
    """CLI command registration and configuration.

    Call :meth:`configure` to configure the CLI provider.

    Usage::

        from quadkit.cli.config import CLIConfig

        @module(
            imports=[CLIModule.configure(CLIConfig(...))]
        )
        class AppModule(Module):
            pass
    """

    @classmethod
    def configure(cls, config: Any | None = None) -> DynamicModule:
        """Create a CLIModule with explicit configuration.

        Args:
            config: :class:`~quadkit.cli.config.CLIConfig` or ``None``
                for framework defaults.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.cli.di.provider import CLIProvider

        return DynamicModule(
            module=cls,
            providers=[CLIProvider(config=config)],
            exports=[CLIApplicationProtocol],
        )

    @classmethod
    def stub(cls, config: Any = None) -> DynamicModule:
        """Return a no-op CLIModule for testing.

        Registers the CLI provider with default configuration.
        No commands are registered by default.

        Returns:
            A DynamicModule with default CLI configuration.
        """
        from quadkit.cli.di.provider import CLIProvider

        return DynamicModule(
            module=cls,
            providers=[CLIProvider()],
            exports=[CLIApplicationProtocol],
        )


__all__ = ["CLIModule"]
