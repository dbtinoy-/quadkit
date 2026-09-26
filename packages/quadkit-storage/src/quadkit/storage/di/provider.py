"""Storage provider for dependency injection."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Self, cast

from quadkit.contracts import (
    BlobStoreProtocol,
    HealthCheckResult,
    HealthStatus,
    ProviderPriority,
)
from quadkit.contracts.core import HealthCheckCategory
from quadkit.contracts.core.config import ConfigProtocol
from quadkit.di.provider import Provider
from quadkit.logging import get_logger
from quadkit.storage import constants as storage_const
from quadkit.storage.backends.registry import DriverRegistry
from quadkit.storage.config import StorageConfig

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Module-level per-driver validator functions
# ---------------------------------------------------------------------------


def _validate_s3(driver_type: str, drivers: dict[str, Any]) -> None:
    """Validate required S3 driver configuration fields."""
    cfg = drivers.get(driver_type)
    if cfg is None:
        raise ValueError(
            f"Storage driver {driver_type!r} requires a 'drivers.{driver_type}' "
            "configuration block with at least 'bucket' and 'region'."
        )
    # Handle both objects and dicts (env vars create dicts)
    bucket = (
        cfg.get("bucket") if isinstance(cfg, dict) else getattr(cfg, "bucket", None)
    )
    region = (
        cfg.get("region") if isinstance(cfg, dict) else getattr(cfg, "region", None)
    )
    if not bucket:
        raise ValueError(
            f"Storage driver {driver_type!r} requires 'drivers.{driver_type}.bucket' to be set."
        )
    if not region:
        raise ValueError(
            f"Storage driver {driver_type!r} requires 'drivers.{driver_type}.region' to be set."
        )


def _validate_gcs(driver_type: str, drivers: dict[str, Any]) -> None:
    """Validate required GCS driver configuration fields."""
    cfg = drivers.get(driver_type)
    if cfg is None:
        raise ValueError(
            f"Storage driver {driver_type!r} requires a 'drivers.{driver_type}' "
            "configuration block with at least 'bucket' and 'project_id'."
        )
    bucket = (
        cfg.get("bucket") if isinstance(cfg, dict) else getattr(cfg, "bucket", None)
    )
    project_id = (
        cfg.get("project_id")
        if isinstance(cfg, dict)
        else getattr(cfg, "project_id", None)
    )
    if not bucket:
        raise ValueError(
            f"Storage driver {driver_type!r} requires 'drivers.{driver_type}.bucket' to be set."
        )
    if not project_id:
        raise ValueError(
            f"Storage driver {driver_type!r} requires 'drivers.{driver_type}.project_id' to be set."
        )


def _validate_azure(driver_type: str, drivers: dict[str, Any]) -> None:
    """Validate required Azure driver configuration fields."""
    cfg = drivers.get(driver_type)
    if cfg is None:
        raise ValueError(
            f"Storage driver {driver_type!r} requires a 'drivers.{driver_type}' "
            "configuration block with 'account_name', 'account_key', and 'container'."
        )
    account_name = (
        cfg.get("account_name")
        if isinstance(cfg, dict)
        else getattr(cfg, "account_name", None)
    )
    account_key = (
        cfg.get("account_key")
        if isinstance(cfg, dict)
        else getattr(cfg, "account_key", None)
    )
    container = (
        cfg.get("container")
        if isinstance(cfg, dict)
        else getattr(cfg, "container", None)
    )
    if not account_name:
        raise ValueError(
            f"Storage driver {driver_type!r} requires 'drivers.{driver_type}.account_name' to be set."
        )
    if not account_key:
        raise ValueError(
            f"Storage driver {driver_type!r} requires 'drivers.{driver_type}.account_key' to be set."
        )
    if not container:
        raise ValueError(
            f"Storage driver {driver_type!r} requires 'drivers.{driver_type}.container' to be set."
        )


def _validate_r2(driver_type: str, drivers: dict[str, Any]) -> None:
    """Validate required Cloudflare R2 driver configuration fields."""
    cfg = drivers.get(driver_type)
    if cfg is None:
        raise ValueError(
            f"Storage driver {driver_type!r} requires a 'drivers.{driver_type}' "
            "configuration block with 'bucket', 'access_key', 'secret_key', and 'endpoint_url'."
        )
    for field in ("bucket", "access_key", "secret_key", "endpoint_url"):
        if not getattr(cfg, field, None):
            raise ValueError(
                f"Storage driver {driver_type!r} requires 'drivers.{driver_type}.{field}' to be set."
            )


# Registry: driver type → validator callable.
# Drivers not listed here (local, memory) require no config validation.
_DRIVER_CONFIG_VALIDATORS: dict[str, Callable[[str, dict[str, Any]], None]] = {
    storage_const.DRIVER_S3: _validate_s3,
    storage_const.DRIVER_GCS: _validate_gcs,
    storage_const.DRIVER_AZURE: _validate_azure,
    storage_const.DRIVER_R2: _validate_r2,
}


class StorageProvider(Provider):
    """DI provider for storage services.

    Registers both the :class:`~quadkit.storage.backends.registry.DriverRegistry`
    (for extensibility) and the configured :class:`~quadkit.contracts.BlobStoreProtocol`
    driver singleton into the container.

    Usage::

        # Pass config directly
        app.add_provider(StorageProvider(config=StorageConfig()))

        # Or let the provider resolve config from the container (requires ConfigProvider)
        app.add_provider(StorageProvider())

        # Later in a service:
        class MyService:
            def __init__(self, store: BlobStoreProtocol) -> None: ...
    """

    name = "storage"
    priority = ProviderPriority.INFRASTRUCTURE
    config_key: str | None = "storage"
    config_model: type | None = StorageConfig

    def __init__(self, config: StorageConfig | None = None) -> None:
        super().__init__()
        self._config = config
        self._config_from_factory = config is not None
        self._driver_registry: DriverRegistry = DriverRegistry()
        self._drivers: list[tuple[str, BlobStoreProtocol]] = []

    @property
    def config(self) -> StorageConfig | None:
        """Return the storage configuration."""
        return cast("StorageConfig | None", self._config)

    @config.setter
    def config(self, value: StorageConfig | None) -> None:
        """Set the storage configuration."""
        self._config = value

    @classmethod
    def from_config(cls, config: StorageConfig, **context: Any) -> Self:
        """Create provider from config object."""
        return cls(config=config)

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register storage services into the DI container.

        If no config was supplied at construction time, resolves it from the
        container via :class:`~quadkit.contracts.core.config.ConfigProtocol`.
        Binds:

        - :class:`~quadkit.storage.backends.registry.DriverRegistry` — the
          extensible driver factory (singleton).
        - :class:`~quadkit.contracts.BlobStoreProtocol` — the configured backend driver
          instance (singleton). In multi-backend mode, also registers named bindings.

        Args:
            container: DI registrar supplied by the framework.
        """
        container.singleton(DriverRegistry, self._driver_registry)

        if self._config is None:
            from quadkit.storage.config import StorageConfig

            resolver = cast("ContainerResolverProtocol", container)
            config_loader = await resolver.resolve(ConfigProtocol)
            self._config = config_loader.get_section("storage", StorageConfig)

        if self._config.backends:
            await self._register_multi_backend(container)
        else:
            await self._register_single_backend(container)

        await self._discover_backends(container)

    async def _register_single_backend(
        self, container: ContainerRegistrarProtocol
    ) -> None:
        """Register a single (unnamed) BlobStoreProtocol binding.

        Args:
            container: DI registrar supplied by the framework.
        """
        self._validate_driver_config(self._config)
        driver_type = self._config.default_driver
        driver: BlobStoreProtocol = self._driver_registry.get_driver(
            driver_type, self._config
        )
        self._driver = driver
        container.singleton(BlobStoreProtocol, driver)

    async def _register_multi_backend(
        self, container: ContainerRegistrarProtocol
    ) -> None:
        """Register multiple named BlobStoreProtocol backends.

        Each entry in ``config.backends`` is registered under its name via a
        named singleton binding.  The first entry (or the one with
        ``primary=True``) also receives the unnamed binding for backward
        compatibility.

        Args:
            container: DI registrar supplied by the framework.
        """
        from quadkit.storage.config import StorageConfig as _StorageConfig

        for entry in self._config.backends:
            backend_cfg = _StorageConfig.from_named(entry)
            driver = self._driver_registry.get_driver(entry.driver, backend_cfg)
            self._drivers.append((entry.name, driver))

            container.singleton(
                BlobStoreProtocol, factory=lambda d=driver: d, name=entry.name
            )

            if entry.primary or self._config.backends[0] is entry:
                self._driver = driver
                container.singleton(BlobStoreProtocol, factory=lambda d=driver: d)

    def _validate_driver_config(self, config: StorageConfig) -> None:
        """Validate required configuration fields for the selected driver.

        Dispatches to the appropriate per-driver validator in
        :data:`_DRIVER_CONFIG_VALIDATORS`.  Drivers not listed there
        (``local``, ``memory``) require no upfront config validation.

        Args:
            config: The resolved storage configuration to validate.

        Raises:
            ValueError: If a required field for the selected driver is missing.
        """
        validator = _DRIVER_CONFIG_VALIDATORS.get(config.default_driver)
        if validator is not None:
            validator(config.default_driver, config.drivers or {})

    async def _discover_backends(self, container: ContainerRegistrarProtocol) -> None:
        """Scan the ``quadkit.storage.backends`` entry-point group.

        Any entry point that resolves to a
        :class:`~quadkit.di.provider.Provider` subclass is instantiated
        and its :meth:`~quadkit.di.provider.Provider.register` method is
        called, allowing third-party backend packages to self-register.

        Args:
            container: The DI container registrar.
        """
        import importlib.metadata as _meta

        from quadkit.di.provider import Provider as _Provider

        eps = _meta.entry_points(group="quadkit.storage.backends")
        for ep in eps:
            try:
                candidate = ep.load()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "storage_ep_load_failed",
                    entry_point=ep.name,
                    error=str(exc),
                )
                continue
            if not (isinstance(candidate, type) and issubclass(candidate, _Provider)):
                logger.debug(
                    "storage_ep_skipped",
                    entry_point=ep.name,
                    reason="not a Provider subclass",
                )
                continue
            logger.debug(
                "storage_ep_found",
                entry_point=ep.name,
                provider=candidate.__name__,
            )
            try:
                await candidate().register(container)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "storage_ep_register_failed",
                    entry_point=ep.name,
                    provider=candidate.__name__,
                    error=str(exc),
                )

    async def _health_check_driver(self, driver: BlobStoreProtocol, name: str) -> None:
        """Run a health check on a single driver, raising on failure or timeout.

        Args:
            driver: The driver to health-check.
            name: Backend name (used in error messages).
        """
        timeout = self._config.health_check_timeout if self._config else 5.0
        if hasattr(driver, "health_check"):
            try:
                health = await asyncio.wait_for(driver.health_check(), timeout=timeout)
            except TimeoutError as exc:
                raise RuntimeError(f"Storage [{name}] health check timed out") from exc
            if health.status != HealthStatus.HEALTHY:
                raise RuntimeError(
                    f"Storage [{name}] health check failed: {health.status}"
                )

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Startup hook — verify storage connectivity after all registrations."""
        if self._drivers:
            results = await asyncio.gather(
                *(self._health_check_driver(d, name) for name, d in self._drivers),
                return_exceptions=True,
            )
            errors = [r for r in results if isinstance(r, BaseException)]
            if errors:
                raise RuntimeError(f"Storage boot failed: {errors[0]}") from errors[0]
        elif hasattr(self, "_driver") and hasattr(self._driver, "health_check"):
            timeout = (
                self._config.health_check_timeout
                if hasattr(self, "_config") and self._config is not None
                else 5.0
            )
            try:
                health = await asyncio.wait_for(
                    self._driver.health_check(),
                    timeout=timeout,
                )
            except TimeoutError as exc:
                raise RuntimeError(
                    f"Storage startup health check timed out after {timeout}s"
                ) from exc
            if health.status != HealthStatus.HEALTHY:
                raise RuntimeError(
                    f"Storage startup health check failed: {health.error or health.status}",
                )
        elif hasattr(self, "_driver") and hasattr(self._driver, "exists"):
            try:
                await self._driver.exists("_health_check")
            except Exception as e:
                raise RuntimeError("Storage startup health check failed") from e

    async def shutdown(self) -> None:
        """Shutdown hook - cleanup resources owned by driver."""
        if self._drivers:
            for _, driver in reversed(self._drivers):
                if hasattr(driver, "close"):
                    try:
                        close = driver.close
                        if asyncio.iscoroutinefunction(close):
                            await close()
                        else:
                            close()
                    except Exception as e:  # noqa: BLE001 — one driver's close failure must not skip closing the rest
                        logger.warning("storage_shutdown_error", error=str(e))
        elif hasattr(self, "_driver") and hasattr(self._driver, "close"):
            try:
                close = self._driver.close
                if asyncio.iscoroutinefunction(close):
                    await close()
                else:
                    close()
            except Exception as e:  # noqa: BLE001 — best-effort shutdown
                logger.warning("storage_shutdown_error", error=str(e))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Health check for storage."""
        import time

        start = time.time()
        if self._drivers:
            results = await asyncio.gather(
                *(
                    d.health_check(timeout=timeout)
                    for _, d in self._drivers
                    if hasattr(d, "health_check")
                ),
                return_exceptions=True,
            )
            worst = HealthStatus.HEALTHY
            for r in results:
                if isinstance(r, BaseException) or r.status == HealthStatus.UNHEALTHY:
                    worst = HealthStatus.UNHEALTHY
                elif (
                    r.status == HealthStatus.DEGRADED
                    and worst != HealthStatus.UNHEALTHY
                ):
                    worst = HealthStatus.DEGRADED
            return HealthCheckResult(
                component="storage",
                status=worst,
                duration_ms=(time.time() - start) * 1000,
                category=HealthCheckCategory.READINESS,
            )
        start_time = time.time()
        if hasattr(self, "_driver") and hasattr(self._driver, "health_check"):
            res = await self._driver.health_check()
            if res.duration_ms == 0.0:
                res.duration_ms = (time.time() - start_time) * 1000  # type: ignore[misc]
            return res

        duration_ms = (time.time() - start_time) * 1000
        return HealthCheckResult(
            component="storage",
            status=HealthStatus.HEALTHY,
            details={"driver": self._config.default_driver or "unknown"},
            duration_ms=duration_ms,
            category=HealthCheckCategory.READINESS,
        )


__all__ = ["StorageProvider"]
