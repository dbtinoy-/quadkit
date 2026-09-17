"""Provider registry and installer for the add command.

Provides lookup/discovery over the provider catalog and utilities to
install provider packages and merge their config into application.yaml.
"""

from __future__ import annotations

import subprocess

from quadkit.cli.package_names import provider_available
from quadkit.cli.registry.provider_catalog import (
    AdminProvider,
    AIProvider,
    AuthProvider,
    CacheProvider,
    CommonProvider,
    ConnectProvider,
    DatabaseService,
    EventsProvider,
    GraphQLProvider,
    MessagingProvider,
    MonitoringProvider,
    MonitorProvider,
    NotificationProvider,
    Provider,
    QueueProvider,
    ResilienceProvider,
    SearchProvider,
    StorageProvider,
    TasksProvider,
    TestingProvider,
    WebProvider,
)


class ProviderRegistry:
    """Registry for Quadkit providers.

    Provides a pluggable way to add new providers.
    """

    def __init__(self) -> None:
        self._providers: dict[str, Provider] = {}

    def register(self, provider: type[Provider]) -> None:
        """Register a provider class."""
        instance = provider()
        self._providers[provider.name] = instance

    def get(self, name: str) -> Provider | None:
        """Get a provider by name."""
        return self._providers.get(name)

    def get_all(self) -> dict[str, Provider]:
        """Get all registered providers."""
        return self._providers.copy()

    def get_choices(self) -> list[str]:
        """Get list of available provider names."""
        return list(self._providers.keys())

    @classmethod
    def _default_entries(cls) -> tuple[type[Provider], ...]:
        """Return core providers plus providers advertised by installed plugins.

        Optional provider classes remain available to the integrated workspace,
        but are not registered in a public installation unless their provider
        distribution is actually installed. This keeps ``quadkit add`` from
        advertising unavailable packages.
        """

        core_entries: tuple[type[Provider], ...] = (
            ConnectProvider,
            ResilienceProvider,
            TestingProvider,
            WebProvider,
        )
        optional_entries: tuple[type[Provider], ...] = (
            DatabaseService,
            AuthProvider,
            AIProvider,
            CacheProvider,
            QueueProvider,
            MessagingProvider,
            NotificationProvider,
            EventsProvider,
            SearchProvider,
            StorageProvider,
            MonitorProvider,
            TasksProvider,
            GraphQLProvider,
            MonitoringProvider,
            AdminProvider,
            CommonProvider,
        )
        return core_entries + tuple(
            entry for entry in optional_entries if provider_available(entry.name)
        )

    @classmethod
    def with_defaults(cls) -> ProviderRegistry:
        """Return an instance populated with the built-in providers."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


class ProviderInstaller:
    """Utility for installing providers."""

    @staticmethod
    def install_provider(provider: Provider) -> bool:
        """Install a provider package using uv."""
        info = provider.get_info()
        try:
            result = subprocess.run(  # noqa: S603 — argv list, no shell
                ["uv", "add", info.package],  # noqa: S607 — static CLI tool on PATH (operator-invoked)
                check=False,
                capture_output=True,
                text=True,
            )
            return result.returncode == 0
        except Exception:  # noqa: BLE001 — provider check degrades to False
            return False

    @staticmethod
    def add_provider_config(
        provider: Provider,
        config_path: str = "application.yaml",
    ) -> bool:
        """Add provider configuration to application.yaml."""
        from pathlib import Path

        import yaml

        info = provider.get_info()
        config_file = Path(config_path)

        if not config_file.exists():
            return False

        try:
            with open(config_file) as f:
                config_data = yaml.safe_load(f) or {}

            for key, value in info.config.items():
                if key not in config_data:
                    config_data[key] = value

            with open(config_file, "w") as f:
                yaml.dump(config_data, f, sort_keys=False)

            return True
        except Exception:  # noqa: BLE001 — provider check degrades to False
            return False


__all__ = ["ProviderInstaller", "ProviderRegistry"]
