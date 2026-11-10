"""MailerProvider — DI provider for email delivery backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.contracts.mailer.protocols import MailerProtocol
from quadkit.contracts.notification.delivery import DeliveryStoreProtocol
from quadkit.di.provider import Provider
from quadkit.logging import get_logger
from quadkit.notification.config import (
    MailerConfig,
    NamedMailerConfig,
)
from quadkit.notification.mailer.backends.registry import MailerBackendRegistry

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


class MailerProvider(Provider):
    """Register SMTP and SendGrid mailer backends into the DI container.

    Reads :class:`~quadkit.notification.config.MailerConfig`, creates the
    appropriate mailer backends, and registers them as
    :class:`~quadkit.contracts.mailer.protocols.MailerProtocol`.

    Dual-mode configuration: an explicit ``config`` wins; otherwise the
    typed ``mailer`` yaml section injected by the orchestrator (via
    ``config_key``) is used; otherwise defaults apply.

    Supports multi-backend (``MailerConfig.backends``) mode. Each entry is
    registered under its name via ``container.singleton(name=entry.name)``.
    The primary backend (``primary=True`` or the first entry) also receives
    the unnamed binding for constructor injection without ``Named``.

    When ``MailerConfig.retry_max_attempts`` is greater than zero the primary
    binding is wrapped in
    :class:`~quadkit.notification.mailer.retrying_mailer.RetryingMailer`, so
    transient transport failures are retried with exponential back-off and
    every attempt is recorded through a
    :class:`~quadkit.contracts.notification.delivery.DeliveryStoreProtocol`:
    ``SqlDeliveryStore`` when the application binds a
    ``DatabaseProviderProtocol``, ``MemoryDeliveryStore`` otherwise. Named
    bindings stay unwrapped — the knob configures the default mailer.
    """

    name = "mailer"
    priority = ProviderPriority.INFRASTRUCTURE
    config_key: str | None = "mailer"
    config_model: type | None = MailerConfig

    def __init__(
        self,
        config: MailerConfig | None = None,
        *,
        backend_registry: MailerBackendRegistry | None = None,
    ) -> None:
        super().__init__()
        self._requested_config = config
        self._config: MailerConfig | None = config
        self._backend_registry = (
            backend_registry or MailerBackendRegistry.with_defaults()
        )
        self._mailers: list[tuple[str, Any]] = []

    @classmethod
    def from_config(cls, config: MailerConfig, **context: Any) -> MailerProvider:
        """Factory method for DI container setup.

        Args:
            config: Mailer configuration.
            **context: Ignored extra context.

        Returns:
            A new :class:`MailerProvider` instance.
        """
        return cls(config)

    def _create_mailer(self, entry: NamedMailerConfig) -> Any:
        """Instantiate the correct mailer implementation for a config entry.

        Args:
            entry: Named mailer configuration entry.

        Returns:
            A mailer instance conforming to :class:`MailerProtocol`.
        """
        return self._backend_registry.create_backend(entry.driver, entry)

    def _delivery_store_factory(self) -> Any:
        """Create the single container-owned delivery store lazily.

        The database provider may register in parallel with the mailer provider,
        so resolution happens when a consumer first asks for the store.
        """
        from quadkit.notification.delivery.stores import (
            MemoryDeliveryStore,
            SqlDeliveryStore,
        )

        async def _factory(resolver: Any = None) -> Any:
            if resolver is None:
                return MemoryDeliveryStore()
            from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
            from quadkit.di.provider_utils import resolve_optional

            provider = await resolve_optional(resolver, DatabaseProviderProtocol)
            if provider is None:
                return MemoryDeliveryStore()
            return SqlDeliveryStore(provider)

        return _factory

    def _runtime_factory(self, mailer: Any) -> Any:
        """Expose the raw configured backend with the shared durable store."""
        from quadkit.notification.delivery.stores import MemoryDeliveryStore
        from quadkit.notification.mailer.runtime import MailerDeliveryRuntime

        async def _factory(resolver: Any = None) -> MailerDeliveryRuntime:
            store = None
            if resolver is not None:
                from quadkit.di.provider_utils import resolve_optional

                store = await resolve_optional(resolver, DeliveryStoreProtocol)
            return MailerDeliveryRuntime(
                backend=mailer,
                delivery_store=store or MemoryDeliveryStore(),
            )

        return _factory

    def _retrying_factory(self, mailer: Any) -> Any:
        """Build an inline retry wrapper over the shared delivery store."""
        from quadkit.notification.delivery.stores import MemoryDeliveryStore
        from quadkit.notification.mailer.retrying_mailer import RetryingMailer

        max_attempts = self._config.retry_max_attempts if self._config else 0
        base_delay = self._config.retry_base_delay if self._config else 1.0

        async def _factory(resolver: Any = None) -> Any:
            store = None
            if resolver is not None:
                from quadkit.di.provider_utils import resolve_optional

                store = await resolve_optional(resolver, DeliveryStoreProtocol)
            store = store or MemoryDeliveryStore()
            logger.debug(
                "mailer_retry_wrapped",
                max_attempts=max_attempts,
                base_delay=base_delay,
                store=type(store).__name__,
            )
            return RetryingMailer(
                inner=mailer,
                delivery_store=store,
                max_attempts=max_attempts,
                base_delay=base_delay,
            )

        return _factory

    @property
    def _retries_enabled(self) -> bool:
        """Whether the primary binding should be retry-wrapped."""
        return bool(self._config and self._config.retry_max_attempts > 0)

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Bind all mailer backends into the container.

        When no backends are configured and ``console_fallback`` is enabled,
        a :class:`~quadkit.notification.mailer.console_mailer.ConsoleMailer`
        is bound as the default ``MailerProtocol`` so outgoing emails are
        logged to the console instead of being silently dropped.

        Args:
            container: DI registrar received from the framework.
        """
        injected = self.config if isinstance(self.config, MailerConfig) else None
        self._config = self._requested_config or injected or MailerConfig()
        container.singleton(MailerConfig, self._config)
        container.singleton(
            DeliveryStoreProtocol,
            factory=self._delivery_store_factory(),
        )

        for entry in self._config.backends:
            mailer = self._create_mailer(entry)
            self._mailers.append((entry.name, mailer))
            container.singleton(
                MailerProtocol,
                factory=lambda _resolver, m=mailer: m,
                name=entry.name,
            )
            is_primary = entry.primary or (
                not any(e.primary for e in self._config.backends)
                and self._config.backends[0] is entry
            )
            if is_primary:
                from quadkit.notification.mailer.runtime import MailerDeliveryRuntime

                container.singleton(
                    MailerDeliveryRuntime,
                    factory=self._runtime_factory(mailer),
                )
                container.singleton(
                    MailerProtocol,
                    factory=(
                        self._retrying_factory(mailer)
                        if self._retries_enabled
                        else lambda _resolver, m=mailer: m
                    ),
                )

        if not self._config.backends and self._config.console_fallback:
            from quadkit.notification.mailer.console_mailer import ConsoleMailer

            console = ConsoleMailer()
            self._mailers.append(("console", console))
            from quadkit.notification.mailer.runtime import MailerDeliveryRuntime

            container.singleton(
                MailerDeliveryRuntime,
                factory=self._runtime_factory(console),
            )
            container.singleton(
                MailerProtocol,
                factory=lambda _resolver, m=console: m,
            )

        logger.info(
            "mailer_registered",
            backends=[n for n, _ in self._mailers],
            retry_max_attempts=self._config.retry_max_attempts,
        )

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """No-op boot; mailers are stateless and require no startup.

        Args:
            container: DI resolver (unused).
        """

    async def shutdown(self) -> None:
        """Clear registered mailer references."""
        self._mailers.clear()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Aggregate health across all registered mailer backends.

        Args:
            timeout: Per-backend health-check timeout in seconds.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        import asyncio

        if not self._mailers:
            return HealthCheckResult(
                component="mailer",
                status=HealthStatus.HEALTHY,
                details={"backends": []},
            )

        results = await asyncio.gather(
            *[
                svc.health_check(timeout=timeout)
                for _, svc in self._mailers
                if hasattr(svc, "health_check")
            ],
            return_exceptions=True,
        )
        worst = HealthStatus.HEALTHY
        details: dict[str, Any] = {}
        for (name, _), result in zip(self._mailers, results, strict=False):
            if isinstance(result, Exception):
                worst = HealthStatus.UNHEALTHY
                details[name] = {"status": "error", "error": str(result)}
            elif isinstance(result, HealthCheckResult):
                details[name] = {"status": result.status.value}
                if result.status == HealthStatus.UNHEALTHY:
                    worst = HealthStatus.UNHEALTHY
                elif (
                    result.status == HealthStatus.DEGRADED
                    and worst == HealthStatus.HEALTHY
                ):
                    worst = HealthStatus.DEGRADED

        return HealthCheckResult(
            component="mailer",
            status=worst,
            details=details,
        )


__all__ = ["MailerProvider"]
