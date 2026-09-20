"""Provider registry for the add command.

This module provides a registry pattern for Quadkit providers/packages.
The catalog of built-in providers lives in ``provider_catalog`` and the
registry/installer plumbing in ``provider_registry``; both are re-exported
here so the public import paths are unchanged.
"""

from __future__ import annotations

from quadkit.cli.registry.provider_catalog import (
    AdminProvider as AdminProvider,
)
from quadkit.cli.registry.provider_catalog import (
    AIProvider as AIProvider,
)
from quadkit.cli.registry.provider_catalog import (
    AuthProvider as AuthProvider,
)
from quadkit.cli.registry.provider_catalog import (
    CacheProvider as CacheProvider,
)
from quadkit.cli.registry.provider_catalog import (
    CommonProvider as CommonProvider,
)
from quadkit.cli.registry.provider_catalog import (
    ConnectProvider as ConnectProvider,
)
from quadkit.cli.registry.provider_catalog import (
    DatabaseService as DatabaseService,
)
from quadkit.cli.registry.provider_catalog import (
    EventsProvider as EventsProvider,
)
from quadkit.cli.registry.provider_catalog import (
    GraphQLProvider as GraphQLProvider,
)
from quadkit.cli.registry.provider_catalog import (
    MessagingProvider as MessagingProvider,
)
from quadkit.cli.registry.provider_catalog import (
    MonitoringProvider as MonitoringProvider,
)
from quadkit.cli.registry.provider_catalog import (
    MonitorProvider as MonitorProvider,
)
from quadkit.cli.registry.provider_catalog import (
    NotificationProvider as NotificationProvider,
)
from quadkit.cli.registry.provider_catalog import (
    Provider as Provider,
)
from quadkit.cli.registry.provider_catalog import (
    ProviderInfo as ProviderInfo,
)
from quadkit.cli.registry.provider_catalog import (
    QueueProvider as QueueProvider,
)
from quadkit.cli.registry.provider_catalog import (
    ResilienceProvider as ResilienceProvider,
)
from quadkit.cli.registry.provider_catalog import (
    SearchProvider as SearchProvider,
)
from quadkit.cli.registry.provider_catalog import (
    StorageProvider as StorageProvider,
)
from quadkit.cli.registry.provider_catalog import (
    TasksProvider as TasksProvider,
)
from quadkit.cli.registry.provider_catalog import (
    TestingProvider as TestingProvider,
)
from quadkit.cli.registry.provider_catalog import (
    WebProvider as WebProvider,
)
from quadkit.cli.registry.provider_registry import (
    ProviderInstaller as ProviderInstaller,
)
from quadkit.cli.registry.provider_registry import (
    ProviderRegistry as ProviderRegistry,
)

__all__ = [
    "AIProvider",
    "AdminProvider",
    "AuthProvider",
    "CacheProvider",
    "CommonProvider",
    "ConnectProvider",
    "DatabaseService",
    "EventsProvider",
    "GraphQLProvider",
    "MessagingProvider",
    "MonitorProvider",
    "MonitoringProvider",
    "NotificationProvider",
    "Provider",
    "ProviderInfo",
    "ProviderInstaller",
    "ProviderRegistry",
    "QueueProvider",
    "ResilienceProvider",
    "SearchProvider",
    "StorageProvider",
    "TasksProvider",
    "TestingProvider",
    "WebProvider",
]
