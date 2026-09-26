"""Cache DI provider."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from quadkit.cache.service.core import CacheService
    from quadkit.contracts import CacheBackendProtocol

# Import from root config.py - Single source of truth
from quadkit.cache.config import (
    CacheConfig,
)
from quadkit.cache.service.health import get_health_status as _get_health_status
from quadkit.cache.service.health import get_metrics as _get_metrics
from quadkit.cache.service.stampede import StampedeProtectedCache
from quadkit.contracts.core import (
    HealthCheckCategory,
    HealthCheckResult,
    ProviderPriority,
)
from quadkit.di.provider import Provider
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts import ContainerResolverProtocol

logger = get_logger(__name__)

T = TypeVar("T")

from quadkit.cache.di._registration import _CacheRegistrationMixin
from quadkit.cache.di._services import _CacheServicesMixin
from quadkit.di.provider import Provider


class CacheProvider(
    _CacheRegistrationMixin,
    _CacheServicesMixin,
    Provider,
):
    """
    Quadkit Cache provider for quadkit integration.

    Integrates cache services with quadkit's provider system,
    managing lifecycle, configuration, and service registration.
    """

    name = "cache"
    priority = ProviderPriority.INFRASTRUCTURE
    config_key: str | None = "cache"
    config_model: type | None = CacheConfig

    def __init__(self, config: CacheConfig | None = None) -> None:
        """Initialize the cache provider.

        Args:
            config: Optional cache configuration. When provided the provider is
                configured immediately (equivalent to calling :meth:`configure`).
        """
        super().__init__()
        self.config: CacheConfig | None = None
        self._services: dict[str, CacheService] = {}
        self._backends: dict[str, CacheBackendProtocol] = {}
        self._serializers: dict[str, Any] = {}
        self._protection: StampedeProtectedCache | None = None
        self._observed_pairs: list[tuple[Any, Any]] = []
        if config is not None:
            self.configure(config)

    @classmethod
    def from_config(cls, config: CacheConfig, **context: Any) -> CacheProvider:
        """Create a CacheProvider from a CacheConfig.

        The provider is created and immediately configured with the config dict.
        """
        provider = cls()
        provider.configure(
            config.model_dump() if hasattr(config, "model_dump") else config,
        )
        return provider

    def configure(self, config: dict[str, Any] | CacheConfig) -> None:
        """Configure the provider with cache settings."""
        # Explicitly-provided config wins over the orchestrator's ``cache``
        # yaml section injection, mirroring the other infrastructure modules.
        self._config_from_factory = True
        if isinstance(config, CacheConfig):
            self.config = config
        else:
            # Convert dict config to CacheConfig
            self.config = CacheConfig(**config)

        # Initialize synchronously so the provider is usable immediately
        self._initialize_serializers()
        # Defer backend init until register() when container is available
        # self._initialize_backends()
        # Services init here; register() will re-init with protection if needed
        # self._initialize_services()

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Start the cache provider.

        All real I/O initialization (backend connections, protection setup,
        service wiring) happens here, after the container is frozen.

        Args:
            container: The DI container provided by the framework.
        """
        logger.info("Starting Quadkit Cache provider")

        # NOTE: RedisStateStore registration is intentionally delegated to
        # quadkit-sql's provider to avoid cross-extension imports.  If you need
        # a StateStoreProtocol alongside the cache, ensure quadkit-sql is installed and
        # its DatabaseProvider is registered before the CacheProvider.
        await self._initialize_backends(container)

        # Initialize stampede protection using the default backend
        if self.config and self.config.service.enable_protection and self._backends:
            default_backend_name = next(
                (
                    name
                    for name, cfg in zip(
                        self._backends.keys(),
                        self.config.backends,
                        strict=False,
                    )
                    if cfg.default
                ),
                next(iter(self._backends)),
            )
            default_backend = self._backends.get(default_backend_name)
            if default_backend is not None:
                self._protection = StampedeProtectedCache(
                    default_backend,
                    lock_timeout=self.config.service.protection_lock_ttl,
                    lock_wait_timeout=self.config.service.protection_max_wait,
                )
            else:
                logger.warning("No cache backend available, cache protection disabled")

        # Initialize services (sync) — must run after backends and protection are ready
        self._initialize_services()

        for cache_repository, repository in self._observed_pairs:
            cache_repository.observe(repository)

        from quadkit.cache.admin.contributor import CacheAdminContributor

        try:
            contributor = await container.resolve(CacheAdminContributor)
            await contributor.on_admin_boot(container)
        except Exception:  # noqa: BLE001
            logger.warning("cache_admin_contributor_boot_failed")

        logger.info("Quadkit Cache provider started successfully")

    def observe_repository(self, cache_repository: Any, repository: Any) -> None:
        """Queue cache repository observation wiring for provider boot.

        Args:
            cache_repository: Cache repository that exposes ``observe()``.
            repository: Source repository whose mutations should invalidate cache.
        """
        self._observed_pairs.append((cache_repository, repository))

    async def shutdown(self) -> None:
        """Shutdown the cache provider and cleanup resources."""
        logger.info("Shutting down Quadkit Cache provider")

        # Shutdown services
        for service in self._services.values():
            try:
                # Some services may not provide close(); use getattr
                close_fn = getattr(service, "close", None)
                if close_fn is not None:
                    await close_fn()
            except Exception:  # noqa: BLE001 — every service/backend must be closed, even if some fail
                logger.exception("Error closing cache service")

        # Shutdown backends
        for backend in self._backends.values():
            try:
                close_fn = getattr(backend, "close", None)
                if close_fn is not None:
                    await close_fn()
            except Exception:  # noqa: BLE001 — every service/backend must be closed, even if some fail
                logger.exception("Error closing cache backend")

        # Clear references
        self._services.clear()
        self._backends.clear()
        self._serializers.clear()
        self._protection = None

        logger.info("Quadkit Cache provider shutdown complete")

    @property
    def cache(self) -> CacheService:
        """Get the default cache service."""
        return self.get_default_service()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check provider health."""
        result = await self.get_health_status()
        return HealthCheckResult(
            component=result.component,
            status=result.status,
            message=result.message,
            error=result.error,
            duration_ms=result.duration_ms,
            details=result.details,
            checked_at=result.checked_at,
            category=HealthCheckCategory.READINESS,
        )

    async def get_health_status(self) -> HealthCheckResult:
        """Return comprehensive health status of all cache services and backends.

        Returns:
            Structured :class:`~quadkit.contracts.types.HealthCheckResult`.
        """
        return await _get_health_status(self._services, self._backends)

    async def get_metrics(self) -> dict[str, Any]:
        """Return comprehensive metrics from all registered cache services.

        Returns:
            Metrics dictionary with per-service statistics.
        """
        return await _get_metrics(self._services, self._backends, self._protection)


def __getattr__(name: str) -> Any:
    """Lazy-load heavy symbols that are only needed at runtime."""
    if name == "CacheService":
        from quadkit.cache.service.core import CacheService

        return CacheService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["CacheProvider"]
