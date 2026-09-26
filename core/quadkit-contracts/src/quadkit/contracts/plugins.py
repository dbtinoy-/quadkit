"""Plugin descriptor and task-plugin marketplace contracts.

A ``PluginDescriptor`` is metadata-only — discovering it via the
``quadkit.plugins`` entry-point group (``EP_PLUGINS``) never imports or
instantiates the plugin's actual DI ``Provider``. That keeps listing
available plugins (e.g. for an admin UI) cheap even when a plugin's provider
class is heavy to import.

The task-plugin marketplace contract is intentionally metadata/settings only.
It does not prescribe a JavaScript runtime or plugin execution model; those
remain application/runtime concerns. Consumers can share validated marketplace
source values without reaching into a particular settings repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class TaskPluginMarketplaceSource:
    """One configured task-plugin marketplace index source."""

    name: str
    index_url: str


@runtime_checkable
class TaskPluginMarketplaceProtocol(Protocol):
    """Durable read/update boundary for task-plugin marketplace sources."""

    async def get_sources(self) -> list[TaskPluginMarketplaceSource]:
        """Return configured sources in display order."""
        ...

    async def update_sources(
        self,
        sources: list[TaskPluginMarketplaceSource],
    ) -> list[TaskPluginMarketplaceSource]:
        """Validate, persist, and return the configured sources."""
        ...


@dataclass(frozen=True)
class PluginDescriptor:
    """Metadata describing an admin-manageable plugin.

    ``provider_entry_point`` is the entry-point *name* (not dotted path)
    this descriptor maps to within the ``quadkit.providers`` (``EP_PROVIDERS``)
    group — the identifier that goes into the ``disabled`` set passed to
    ``quadkit.plugins.discovery.discover_providers``.

    ``requires``/``conflicts`` name other plugins' ``provider_entry_point``
    values. They are advisory metadata: the boot engine evaluates them via
    ``validate_plan`` and skips plugins whose dependencies are missing or
    whose conflicts are enabled, logging non-fatal issues — boot is never
    blocked.
    """

    name: str
    display_name: str
    description: str
    icon: str
    provider_entry_point: str
    version: str = ""
    requires: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()


__all__ = [
    "PluginDescriptor",
    "TaskPluginMarketplaceProtocol",
    "TaskPluginMarketplaceSource",
]
