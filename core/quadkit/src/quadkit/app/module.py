"""CoreModule — minimal kernel provider manifest for a Quadkit application.

``CoreModule`` pre-registers the four framework-level kernel providers in
dependency order.  These providers are **always-on** services that every
Quadkit application requires: configuration, logging, infrastructure
primitives, and DI introspection.

Kernel providers (boot order governed by provider ``priority`` and ``dependencies``):

    ConfigProvider              (CRITICAL)         — configuration loading
    LoggingProvider             (CRITICAL)         — structured logging
    CoreInfrastructureProvider  (INFRASTRUCTURE)   — context, signals, registries
    DiProvider                  (NORMAL)           — DI introspection config

For a batteries-included bundle that also provides serialization and
concurrency, use :class:`~quadkit.app.standard.StandardModule` instead.

Extension packages (``the optional provider``, ``the optional provider``, ``quadkit-web``,
etc.) register their own providers via ``app.add_provider()`` or
``app.add_module()``.  ``CoreModule`` intentionally imports **only** from
``quadkit-contracts`` and the ``quadkit`` core package — zero cross-package
dependencies.

Usage::

    from quadkit.app import Application, CoreModule

    async with Application.boot(modules=[CoreModule.configure()]) as app:
        ...

Backward-compatible bootstrap (still supported)::

    async with Application.boot(providers=CoreModule.build_providers()) as app:
        ...

Override a default provider::

    module = CoreModule.configure(
        overrides={"config": CustomConfigProvider()},
    )
    async with Application.boot(modules=[module]) as app:
        ...

Extend with additional providers::

    providers = CoreModule.build_providers() + [MyCustomProvider()]
    async with Application.boot(providers=providers) as app:
        ...

.. note::

    ``CoreModule.configure()`` returns a ``DynamicModule`` for module-oriented
    bootstrap while preserving the existing ``build_providers()`` API.
"""

from __future__ import annotations

from typing import Any

from quadkit.config.di.provider import ConfigProvider
from quadkit.contracts.core.clock import ClockProtocol
from quadkit.contracts.core.config import ConfigProtocol
from quadkit.contracts.core.di import ContainerResolverProtocol
from quadkit.contracts.core.identity import IdGeneratorProtocol
from quadkit.contracts.core.logging import (
    LoggerFactoryProtocol,
    LoggerProtocol,
    RedactorProtocol,
)
from quadkit.di.integration.provider import DiProvider
from quadkit.di.module import Module, module
from quadkit.di.module.dynamic import DynamicModule
from quadkit.di.provider import Provider
from quadkit.identity.di.provider import IdentityProvider
from quadkit.logging.di.provider import LoggingProvider
from quadkit.observability.di.sub_providers.observability import ObservabilityProvider
from quadkit.primitives.di.provider import CoreInfrastructureProvider

# ---------------------------------------------------------------------------
# Core provider classes — internal to the quadkit core package.
#
# Ordered by recommended registration sequence.  The orchestrator's
# topological sort (provider ``dependencies`` + ``priority``) determines
# the final boot order; tuple position is advisory only.
#
# Extension providers (mapping, middleware, monitoring, plugins, resilience,
# etc.) belong to their own packages and are NEVER imported here.
# ---------------------------------------------------------------------------

_CORE_PROVIDERS: tuple[type[Provider], ...] = (
    ConfigProvider,  # CRITICAL   — must register first
    LoggingProvider,  # CRITICAL   — depends on config
    CoreInfrastructureProvider,  # INFRA      — context, signals, rate limiter
    IdentityProvider,  # INFRA      — injectable ID generation
    ObservabilityProvider,  # INFRA      — no-op observability fallbacks
    DiProvider,  # NORMAL     — DI container config
)

# ---------------------------------------------------------------------------
# Exported contracts — the public API surface of the core framework.
#
# These are the contract types that CoreModule's providers register
# into the container.  Other modules importing CoreModule gain access
# to these types once module visibility enforcement is active.
# ---------------------------------------------------------------------------


def _get_core_exports() -> list[type]:
    """Return the set of core framework exports.

    References Application lazily to avoid circular imports during
    module decoration.
    """
    from quadkit.app.base import Application
    from quadkit.config.main import QuadkitConfig
    from quadkit.primitives.context import Context, ContextVarRegistry

    return [
        Application,
        ClockProtocol,
        ConfigProtocol,
        IdGeneratorProtocol,
        QuadkitConfig,
        LoggerFactoryProtocol,
        LoggerProtocol,
        RedactorProtocol,
        ContainerResolverProtocol,
        Context,
        ContextVarRegistry,
    ]


_CORE_EXPORTS: list[type] = _get_core_exports()


@module(
    name="CoreModule",
    providers=list(_CORE_PROVIDERS),
    exports=_CORE_EXPORTS,
)
class CoreModule(Module):
    """Kernel provider manifest for a minimal Quadkit application.

    Bundles the four kernel framework providers that every Quadkit application
    requires: configuration, logging, infrastructure primitives, and DI
    introspection.

    For a batteries-included bundle that also provides serialization and
    concurrency, use :class:`~quadkit.app.standard.StandardModule`.

    Extension packages add their own providers separately.  ``CoreModule``
    has **zero cross-package imports** — it references only providers
    defined within the ``quadkit`` core package and contracts from
    ``quadkit-contracts``.
    """

    @classmethod
    def build_providers(
        cls,
        config_class: type[Any] | None = None,
        config_sources: list[Any] | None = None,
        env_prefix: str = "",
        overrides: dict[str, Provider] | None = None,
    ) -> list[Provider]:
        """Instantiate and return the core provider list.

        Creates a fresh provider instance from each registered core provider
        class.  Use *overrides* to replace any default provider by its
        :attr:`~Provider.name`.

        Args:
            config_class: Custom configuration dataclass to use instead of
                the default :class:`~quadkit.config.main.QuadkitConfig`.
            config_sources: Explicit list of
                :class:`~quadkit.config.lib.sources.ConfigSource` instances.
                When ``None``, ``ConfigProvider`` falls back to its default
                source chain (environment variables + config files).
            env_prefix: Environment variable prefix forwarded to the
                ``ConfigProvider``.
            overrides: Mapping of provider **name** → replacement
                :class:`~quadkit.di.provider.Provider` instance.  A name
                matching a core provider replaces that provider; unmatched
                names are appended to the end of the list.

        Returns:
            Ordered list of :class:`~quadkit.di.provider.Provider` instances
            ready to pass to :meth:`Application.boot`.

        Example::

            providers = CoreModule.build_providers(
                config_class=MyConfig,
                overrides={"logging": CustomLoggingProvider()},
            )
        """
        dynamic_module = cls.configure(
            config_class=config_class,
            config_sources=config_sources,
            env_prefix=env_prefix,
            overrides=overrides,
        )

        providers: list[Provider] = []
        for provider in dynamic_module.providers:
            if isinstance(provider, Provider):
                providers.append(provider)

        return providers

    @classmethod
    def configure(
        cls,
        config_class: type[Any] | None = None,
        config_sources: list[Any] | None = None,
        env_prefix: str = "",
        overrides: dict[str, Provider] | None = None,
    ) -> DynamicModule:
        """Create a DynamicModule configured with core provider instances.

        Args:
            config_class: Custom configuration dataclass for ``ConfigProvider``.
            config_sources: Explicit config source list for ``ConfigProvider``.
            env_prefix: Environment variable prefix for ``ConfigProvider``.
            overrides: Mapping of provider name -> replacement provider instance.

        Returns:
            DynamicModule configured with instantiated core providers and
            default core exports.
        """
        override_map: dict[str, Provider] = overrides or {}
        providers: list[Provider] = []
        consumed: set[str] = set()

        for provider_cls in _CORE_PROVIDERS:
            instance = _instantiate_provider(
                provider_cls,
                config_class=config_class,
                config_sources=config_sources,
                env_prefix=env_prefix,
            )

            # Apply override if one exists for this provider name.
            if instance.name in override_map:
                providers.append(override_map[instance.name])
                consumed.add(instance.name)
            else:
                providers.append(instance)

        # Append overrides whose names don't match any core provider,
        # preserving insertion order of the override dict.  Keys that were
        # already applied as replacements must not be appended a second time
        # (the replacement instance no longer carries the core provider name).
        provider_names = {p.name for p in providers}
        for name, provider in override_map.items():
            if name not in consumed and name not in provider_names:
                providers.append(provider)

        return DynamicModule(
            module=cls,
            providers=providers,  # type: ignore[arg-type]
            exports=list(_CORE_EXPORTS),
            is_global=True,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _instantiate_provider(
    provider_cls: type[Provider],
    *,
    config_class: type[Any] | None,
    config_sources: list[Any] | None,
    env_prefix: str,
) -> Provider:
    """Create a single provider instance.

    ``ConfigProvider`` receives forwarded configuration arguments;
    all other providers are default-constructed.
    """
    if issubclass(provider_cls, ConfigProvider):
        from quadkit.config.main import QuadkitConfig

        return provider_cls(
            config_class=config_class or QuadkitConfig,
            sources=config_sources,
            env_prefix=env_prefix,
        )
    return provider_cls()


__all__ = ["CoreModule"]
