"""Entry-point-based provider and plugin-descriptor discovery.

``discover_providers`` is the function ``quadkit/src/quadkit/app/factory.py``'s
own docstring already promises: "Provider auto-discovery via entry points is
the responsibility of ``quadkit-plugins``." It is the *single* implementation
of the discover→filter→load→instantiate path — ``PluginEngineProvider``
(``quadkit.plugins.engine``) delegates its discovery to this primitive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib.metadata import entry_points as _entry_points
from typing import TYPE_CHECKING

from quadkit.contracts.core.constants import EP_PLUGINS, EP_PROVIDERS
from quadkit.contracts.plugins import PluginDescriptor
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.provider import Provider

logger = get_logger(__name__)

__all__ = [
    "PluginPlan",
    "discover_plugins",
    "discover_providers",
    "unique_descriptors",
    "validate_plan",
]


@dataclass(frozen=True)
class PluginPlan:
    """Validated view of plugin enable/disable state.

    Attributes:
        enabled: Entry-point names that are installed and will boot.
        disabled: Entry-point names that are installed but disabled.
        unknown: Disabled names with no matching installed descriptor.
        issues: Human-readable non-fatal validation findings
            (missing dependencies, conflicts) — one string per finding.
    """

    enabled: frozenset[str]
    disabled: frozenset[str]
    unknown: frozenset[str] = frozenset()
    issues: tuple[str, ...] = field(default_factory=tuple)


def discover_providers(disabled: set[str] | None = None) -> list[Provider]:
    """Discover and instantiate providers declared by plugin descriptors.

    Only entry points referenced by an installed ``PluginDescriptor``
    (:group:`EP_PLUGINS`) are considered — framework packages that happen
    to register under ``EP_PROVIDERS`` (admin, auth, sql, web, ...) are
    *not* plugins and are left out; they are composed explicitly by the
    application's module graph instead.

    Args:
        disabled: Entry-point names to skip (e.g. from
            :func:`quadkit.plugins.state.load_disabled`).

    Returns:
        Instantiated ``Provider`` objects for every enabled, constructible
        plugin entry point. Entries that fail to load, aren't a ``Provider``
        subclass, or require constructor arguments are skipped with a log.
    """
    from quadkit.di.provider import Provider

    disabled = disabled or set()
    plugin_entry_points = {d.provider_entry_point for d in discover_plugins()}
    found: list[Provider] = []

    for ep in _entry_points(group=EP_PROVIDERS):
        if ep.name not in plugin_entry_points:
            logger.debug(
                "plugins.discovery.not_plugin_managed",
                name=ep.name,
            )
            continue
        if ep.name in disabled:
            logger.debug("plugins.discovery.skipped_disabled", name=ep.name)
            continue
        try:
            provider_cls = ep.load()
        except Exception:  # noqa: BLE001 — skip bad entry points, continue discovery
            logger.warning("plugins.discovery.entry_point_load_failed", name=ep.name)
            continue
        if not (isinstance(provider_cls, type) and issubclass(provider_cls, Provider)):
            logger.debug(
                "plugins.discovery.not_a_provider",
                name=ep.name,
                loaded=repr(provider_cls),
            )
            continue
        try:
            found.append(provider_cls())
        except Exception:  # noqa: BLE001 — skip unconstructible entry points, continue discovery
            logger.debug(
                "plugins.discovery.skipped_ctor_args",
                name=ep.name,
                reason="unconstructible",
            )

    return found


def discover_plugins() -> list[PluginDescriptor]:
    """Discover all ``PluginDescriptor``s registered under ``EP_PLUGINS``.

    Metadata-only — never imports the plugin's actual ``Provider`` class,
    so this is cheap to call even for listing purposes (e.g. an admin UI).
    """
    found: list[PluginDescriptor] = []
    for ep in _entry_points(group=EP_PLUGINS):
        try:
            descriptor = ep.load()
        except Exception:  # noqa: BLE001 — skip bad entry points, continue discovery
            logger.warning(
                "plugins.discovery.plugin_entry_point_load_failed", name=ep.name
            )
            continue
        if not isinstance(descriptor, PluginDescriptor):
            logger.debug(
                "plugins.discovery.not_a_plugin_descriptor",
                name=ep.name,
                loaded=repr(descriptor),
            )
            continue
        found.append(descriptor)
    return found


def unique_descriptors(descriptors: list[PluginDescriptor]) -> list[PluginDescriptor]:
    """Return descriptors deduplicated by ``provider_entry_point``.

    First occurrence wins (matches entry-point precedence when several
    distributions register the same name).

    Args:
        descriptors: Raw discovered descriptors.

    Returns:
        List with at most one descriptor per ``provider_entry_point``.
    """
    seen: set[str] = set()
    result: list[PluginDescriptor] = []
    for descriptor in descriptors:
        if descriptor.provider_entry_point in seen:
            continue
        seen.add(descriptor.provider_entry_point)
        result.append(descriptor)
    return result


def validate_plan(
    descriptors: list[PluginDescriptor],
    disabled: set[str],
) -> PluginPlan:
    """Compute the validated enable/disable plan for discovered plugins.

    Validation is advisory: missing dependencies and conflicts produce
    issue strings (and exclude the affected plugin from ``enabled``) but
    never raise — a broken plugin must not break the boot.

    Args:
        descriptors: Installed plugin descriptors (discovery output).
        disabled: Disabled entry-point names from the state file.

    Returns:
        A PluginPlan with enabled/disabled/unknown sets and issues.
    """
    unique = unique_descriptors(descriptors)
    by_entry: dict[str, PluginDescriptor] = {d.provider_entry_point: d for d in unique}

    installed = set(by_entry)
    disabled_set = set(disabled)
    unknown = frozenset(disabled_set - installed)
    enabled = installed - disabled_set

    issues: list[str] = []
    enabled_names = set(enabled)
    for entry, descriptor in by_entry.items():
        for required in descriptor.requires:
            if required not in enabled_names:
                issues.append(f"{descriptor.name}: missing dependency {required!r}")
                enabled.discard(entry)
        for conflict in descriptor.conflicts:
            if conflict in enabled_names:
                issues.append(f"{descriptor.name}: conflicts with {conflict!r}")
                enabled.discard(entry)

    return PluginPlan(
        enabled=frozenset(enabled),
        disabled=frozenset(disabled_set & installed),
        unknown=unknown,
        issues=tuple(issues),
    )
