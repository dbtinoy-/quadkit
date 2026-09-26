"""Storage driver registry — maps driver-type strings to factory callables.

Design: a single :class:`DriverRegistry` holds a ``dict[str, DriverFactory]``
where each value is a plain callable that accepts a :class:`StorageConfig` and
returns a :class:`~quadkit.contracts.BlobStoreProtocol`.  There are no per-driver
registry classes — third parties extend the registry by calling
:meth:`DriverRegistry.register`.

The canonical path inside a Quadkit *Application* is to resolve
:class:`DriverRegistry` from the DI container (registered by
:class:`~quadkit.storage.providers.StorageProvider`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from quadkit.contracts import BlobStoreProtocol
from quadkit.storage import constants as storage_const
from quadkit.storage.backends.local import LocalDriver
from quadkit.storage.backends.memory import MemoryDriver

try:
    from quadkit.storage.backends.s3 import S3Driver

    _S3_AVAILABLE = True
except ImportError:
    _S3_AVAILABLE = False
    S3Driver = None  # type: ignore[misc,assignment]

try:
    from quadkit.storage.backends.gcs import GCSDriver

    _GCS_AVAILABLE = True
except ImportError:
    _GCS_AVAILABLE = False
    GCSDriver = None  # type: ignore[misc,assignment]

try:
    from quadkit.storage.backends.azure import AzureDriver

    _AZURE_AVAILABLE = True
except ImportError:
    _AZURE_AVAILABLE = False
    AzureDriver = None  # type: ignore[misc,assignment]

from quadkit.primitives.registry import BackendRegistry as _CoreBackendRegistry

# Type alias for driver factory callables
DriverFactory = Callable[[Any], BlobStoreProtocol]


def _create_memory(config: Any) -> BlobStoreProtocol:
    """Factory: in-memory driver (testing / ephemeral use)."""
    return MemoryDriver()


def _cfg_val(cfg: Any, key: str, default: Any) -> Any:
    """Read a value from a driver config that may be a dict or a Pydantic model."""
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def _create_local(config: Any) -> BlobStoreProtocol:
    """Factory: local filesystem driver."""
    local_cfg: Any = config.drivers.get(storage_const.DRIVER_LOCAL, {})
    return LocalDriver(
        root_dir=_cfg_val(local_cfg, "root_dir", storage_const.DEFAULT_LOCAL_ROOT_DIR),
        base_url=_cfg_val(local_cfg, "base_url", storage_const.DEFAULT_LOCAL_BASE_URL),
    )


def _create_s3(config: Any) -> BlobStoreProtocol:
    """Factory: AWS S3 (or compatible) driver."""
    if not _S3_AVAILABLE:
        raise ImportError(
            "S3 driver requires aiobotocore. "
            "Install with: pip install quadkit-storage[aws]",
        )
    s3_cfg: Any = config.drivers.get(storage_const.DRIVER_S3, {})
    bucket = getattr(s3_cfg, "bucket", None)
    if not bucket:
        raise ValueError("S3 storage driver requires a 'bucket' configuration")
    raw_access_key = getattr(s3_cfg, "access_key", None)
    raw_secret_key = getattr(s3_cfg, "secret_key", None)
    return S3Driver(
        bucket=bucket,
        region=getattr(s3_cfg, "region", None),
        access_key=raw_access_key.get_secret_value() if raw_access_key else None,
        secret_key=raw_secret_key.get_secret_value() if raw_secret_key else None,
        endpoint_url=getattr(s3_cfg, "endpoint_url", None),
        public_url=getattr(s3_cfg, "public_url", None),
    )


def _create_r2(config: Any) -> BlobStoreProtocol:
    """Factory: Cloudflare R2 (S3-compatible) driver."""
    if not _S3_AVAILABLE:
        raise ImportError(
            "R2 driver requires aiobotocore. "
            "Install with: pip install quadkit-storage[aws]",
        )
    r2_cfg: Any = config.drivers.get(storage_const.DRIVER_R2, {})
    bucket = getattr(r2_cfg, "bucket", None)
    endpoint_url = getattr(r2_cfg, "endpoint_url", None)
    raw_access_key = getattr(r2_cfg, "access_key", None)
    raw_secret_key = getattr(r2_cfg, "secret_key", None)
    if not bucket:
        raise ValueError("R2 storage driver requires a 'bucket' configuration")
    if not endpoint_url:
        raise ValueError("R2 storage driver requires an 'endpoint_url' configuration")
    if not raw_access_key:
        raise ValueError("R2 storage driver requires an 'access_key' configuration")
    if not raw_secret_key:
        raise ValueError("R2 storage driver requires a 'secret_key' configuration")
    return S3Driver(
        bucket=bucket,
        region=getattr(r2_cfg, "region", "auto"),
        access_key=raw_access_key.get_secret_value() if raw_access_key else None,
        secret_key=raw_secret_key.get_secret_value() if raw_secret_key else None,
        endpoint_url=endpoint_url,
        public_url=getattr(r2_cfg, "public_url", None),
    )


def _create_gcs(config: Any) -> BlobStoreProtocol:
    """Factory: Google Cloud Storage driver."""
    if not _GCS_AVAILABLE:
        raise ImportError(
            "GCS driver requires gcloud-aio-storage. "
            "Install with: pip install quadkit-storage[gcs]",
        )
    gcs_cfg: Any = config.drivers.get(storage_const.DRIVER_GCS, {})
    bucket = getattr(gcs_cfg, "bucket", None)
    if not bucket:
        raise ValueError("GCS storage driver requires a 'bucket' configuration")
    return GCSDriver(
        bucket=bucket,
        project_id=getattr(gcs_cfg, "project_id", None),
        credentials_path=getattr(gcs_cfg, "credentials_path", None),
    )


def _create_azure(config: Any) -> BlobStoreProtocol:
    """Factory: Azure Blob Storage driver."""
    if not _AZURE_AVAILABLE:
        raise ImportError(
            "Azure driver requires azure-storage-blob. "
            "Install with: pip install quadkit-storage[azure]",
        )
    azure_cfg: Any = config.drivers.get(storage_const.DRIVER_AZURE, {})
    account_name = getattr(azure_cfg, "account_name", None)
    account_key_secret = getattr(azure_cfg, "account_key", None)
    container = getattr(azure_cfg, "container", None)
    if not account_name:
        raise ValueError(
            "Azure storage driver requires an 'account_name' configuration"
        )
    if not account_key_secret:
        raise ValueError("Azure storage driver requires an 'account_key' configuration")
    if not container:
        raise ValueError("Azure storage driver requires a 'container' configuration")
    raw_key = (
        account_key_secret.get_secret_value()
        if hasattr(account_key_secret, "get_secret_value")
        else str(account_key_secret)
    )
    return AzureDriver(
        account_name=account_name,
        account_key=raw_key,
        container=container,
    )


# Default factory mapping for all built-in drivers
_DEFAULT_FACTORIES: dict[str, DriverFactory] = {
    storage_const.DRIVER_MEMORY: _create_memory,
    storage_const.DRIVER_LOCAL: _create_local,
    storage_const.DRIVER_S3: _create_s3,
    storage_const.DRIVER_GCS: _create_gcs,
    storage_const.DRIVER_AZURE: _create_azure,
    storage_const.DRIVER_R2: _create_r2,
}


class DriverRegistry(_CoreBackendRegistry):
    """Central registry that maps driver-type strings to factory callables.

    Extends :class:`quadkit.primitives.registry.BackendRegistry` so that all
    driver registries share a common hierarchy and introspection API.
    Third-party storage drivers can be registered via entry points using
    the ``quadkit.storage.backends`` group.

    Usage::

        # Resolved from DI container (preferred inside Quadkit Application)
        registry = await container.resolve(DriverRegistry)
        driver = registry.get_driver("s3", config)
    """

    def __init__(self) -> None:
        """Initialise with all built-in driver factories (allow overwrite)."""
        super().__init__(name="storage.backends", allow_overwrite=True)
        for driver_type, factory in _DEFAULT_FACTORIES.items():
            super().register(driver_type, factory)

    def register(self, driver_type: str, factory: DriverFactory) -> None:  # type: ignore[override]
        """Register a custom driver factory.

        Overwrites any existing factory registered under *driver_type*.

        Args:
            driver_type: Identifier string (e.g. ``"minio"``, ``"r2"``).
            factory: Callable ``(config: StorageConfig) -> BlobStoreProtocol``.
        """
        super().register(driver_type, factory)

    def get_driver(self, driver_type: str, config: Any) -> BlobStoreProtocol:
        """Instantiate and return a driver for *driver_type*.

        Args:
            driver_type: One of the registered type strings.
            config: :class:`~quadkit.storage.config.StorageConfig` instance.

        Returns:
            A ready-to-use :class:`~quadkit.contracts.BlobStoreProtocol` instance.

        Raises:
            ValueError: If *driver_type* is not registered.
            NotImplementedError: If the driver is declared but not yet built
                (e.g. ``"gcs"``, ``"azure"``).
            ImportError: If a required optional dependency is missing.
        """
        factory = self.get(driver_type)
        if factory is None:
            available = self.available_drivers()
            raise ValueError(
                f"Unknown storage driver: {driver_type!r}. Available: {', '.join(available)}",
            )
        driver: BlobStoreProtocol = factory(config)
        return driver

    def available_drivers(self) -> list[str]:
        """Return a sorted list of all registered driver-type strings."""
        return sorted(self.keys())


__all__ = ["DriverFactory", "DriverRegistry"]
