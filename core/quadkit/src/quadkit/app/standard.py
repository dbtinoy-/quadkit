"""StandardModule — batteries-included provider bundle for production Quadkit applications.

``StandardModule`` is the **superset** of :class:`~quadkit.app.module.CoreModule`.
It adds :class:`~quadkit.serialization.di.provider.SerializationProvider` and
:class:`~quadkit.concurrency.di.provider.ConcurrencyProvider` on top of the
four kernel providers provided by ``CoreModule``.

Standard providers (boot order governed by provider ``priority`` and ``dependencies``):

    ConfigProvider              (CRITICAL)         — configuration loading
    LoggingProvider             (CRITICAL)         — structured logging
    CoreInfrastructureProvider  (INFRASTRUCTURE)   — context, signals, registries
    SerializationProvider       (INFRASTRUCTURE)   — JSON serialization codec
    ConcurrencyProvider         (NORMAL)           — dispatcher, task manager
    DiProvider                  (NORMAL)           — DI introspection config

Use ``StandardModule`` as the default bootstrap module for full-featured
production applications.  Use :class:`~quadkit.app.module.CoreModule` only
when you need a stripped-down kernel without serialization or concurrency
utilities (e.g. embedded runtimes, test harnesses, micro-kernels).

Usage::

    from quadkit.app import Application, StandardModule

    async with Application.boot(modules=[StandardModule.configure()]) as app:
        ...

With a custom config class::

    module = StandardModule.configure(config_class=MyConfig)
    async with Application.boot(modules=[module]) as app:
        ...

Override a provider::

    module = StandardModule.configure(
        overrides={"serialization": CustomSerializationProvider()},
    )
    async with Application.boot(modules=[module]) as app:
        ...

.. note::

    ``StandardModule.configure()`` returns a ``DynamicModule`` for module-oriented
    bootstrap while preserving the existing ``build_providers()`` API.
"""

from __future__ import annotations

from typing import Any

from quadkit.app.module import _get_core_exports
from quadkit.config.di.provider import ConfigProvider
from quadkit.contracts.core.serialization import JsonSerializerProtocol
from quadkit.di.integration.provider import DiProvider
from quadkit.di.module import Module, module
from quadkit.di.module.dynamic import DynamicModule
from quadkit.di.provider import Provider
from quadkit.identity.di.provider import IdentityProvider
from quadkit.logging.di.provider import LoggingProvider
from quadkit.observability.di.sub_providers.observability import ObservabilityProvider
from quadkit.primitives.di.provider import CoreInfrastructureProvider
from quadkit.serialization.di.provider import SerializationProvider

# ---------------------------------------------------------------------------
# Standard provider tuple — all six providers in recommended boot order.
# ---------------------------------------------------------------------------


def _load_standard_providers() -> tuple[type[Provider], ...]:
    """Load the standard provider tuple, lazy-importing the concurrency provider.

    ``ConcurrencyProvider`` lives in ``quadkit-concurrency`` (a separate package)
    to avoid a circular package dependency.  It is always available at runtime
    because the workspace/install always includes ``quadkit-concurrency``.
    """
    from quadkit.concurrency.di.provider import ConcurrencyProvider  # noqa: PLC0415

    return (
        ConfigProvider,  # CRITICAL   — must register first
        LoggingProvider,  # CRITICAL   — depends on config
        CoreInfrastructureProvider,  # INFRA      — context, signals, rate limiter
        IdentityProvider,  # INFRA      — injectable ID generation
        ObservabilityProvider,  # INFRA      — no-op observability fallbacks
        SerializationProvider,  # INFRA      — JSON codec
        ConcurrencyProvider,  # NORMAL     — dispatcher, task manager
        DiProvider,  # NORMAL     — DI container config
    )


_STANDARD_PROVIDERS: tuple[type[Provider], ...] = _load_standard_providers()

# ---------------------------------------------------------------------------
# Exported contracts — the public API surface of the standard bundle.
# ---------------------------------------------------------------------------

_STANDARD_EXPORTS: list[type] = [
    *_get_core_exports(),
    JsonSerializerProtocol,
]


@module(
    name="StandardModule",
    providers=list(_STANDARD_PROVIDERS),
    exports=_STANDARD_EXPORTS,
)
class StandardModule(Module):
    """Batteries-included provider bundle for production Quadkit applications.

    Extends :class:`~quadkit.app.module.CoreModule` with serialization and
    concurrency providers.  Use this as the default bootstrap module for
    full-featured applications.

    CoreModule provides: ConfigProvider, LoggingProvider,
        CoreInfrastructureProvider, DiProvider.
    StandardModule adds: SerializationProvider, ConcurrencyProvider.
    """

    @classmethod
    def build_providers(
        cls,
        config_class: type[Any] | None = None,
        config_sources: list[Any] | None = None,
        env_prefix: str = "",
        overrides: dict[str, Provider] | None = None,
    ) -> list[Provider]:
        """Instantiate and return the standard provider list.

        Creates a fresh provider instance from each registered standard
        provider class.  Use *overrides* to replace any default provider by
        its :attr:`~Provider.name`.

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
                matching a standard provider replaces that provider;
                unmatched names are appended to the end of the list.

        Returns:
            Ordered list of :class:`~quadkit.di.provider.Provider` instances
            ready to pass to :meth:`Application.boot`.

        Example::

            providers = StandardModule.build_providers(
                config_class=MyConfig,
                overrides={"serialization": CustomSerializationProvider()},
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
        """Create a DynamicModule configured with standard provider instances.

        Args:
            config_class: Custom configuration dataclass for ``ConfigProvider``.
            config_sources: Explicit config source list for ``ConfigProvider``.
            env_prefix: Environment variable prefix for ``ConfigProvider``.
            overrides: Mapping of provider name -> replacement provider instance.

        Returns:
            DynamicModule configured with instantiated standard providers and
            default standard exports.
        """
        override_map: dict[str, Provider] = overrides or {}
        providers: list[Any] = []
        consumed: set[str] = set()

        for provider_cls in _STANDARD_PROVIDERS:
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

        # Append overrides whose names don't match any standard provider,
        # preserving insertion order of the override dict.  Keys that were
        # already applied as replacements must not be appended a second time
        # (the replacement instance no longer carries the standard provider name).
        provider_names = {p.name for p in providers}
        for name, provider in override_map.items():
            if name not in consumed and name not in provider_names:
                providers.append(provider)

        return DynamicModule(
            module=cls,
            providers=providers,
            exports=list(_STANDARD_EXPORTS),
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


__all__ = ["StandardModule"]
