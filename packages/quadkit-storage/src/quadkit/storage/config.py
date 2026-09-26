"""Configuration models for Quadkit Storage.

This module provides Pydantic models for configuring storage
backends and operations.

Example:
    from quadkit.storage.config import StorageConfig

    # From YAML
    config = StorageConfig.from_yaml("application.yaml")

    # From environment
    config = StorageConfig()  # reads QK_STORAGE__* env vars
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Literal, cast

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.domain import DomainModel
from quadkit.storage import constants as storage_const
from quadkit.validation import ConfigDict, Field, SecretStr, model_validator


@dataclass(init=False)
class EncryptionConfig(BaseConfig):
    """Server-side encryption configuration for cloud storage backends.

    Supported types:
    - ``"AES256"``: Amazon S3 / GCS default managed encryption (SSE-S3).
    - ``"aws:kms"``: AWS Key Management Service (SSE-KMS).  Requires ``kms_key_id``.
    - ``"gcs:cmek"``: GCS Customer-Managed Encryption Keys.  Requires ``kms_key_id``.

    Example::

        # SSE-S3 (Amazon managed, no key ID needed)
        EncryptionConfig(enabled=True)

        # SSE-KMS with a specific CMK
        EncryptionConfig(enabled=True, type="aws:kms", kms_key_id="arn:aws:kms:…")
    """

    enabled: bool = Field(default=False, description="Enable server-side encryption")
    type: Literal["AES256", "aws:kms", "gcs:cmek"] = Field(
        default="AES256",
        description="Encryption type",
    )
    kms_key_id: str | None = Field(
        default=None,
        description="KMS/CMEK key ARN or ID (required for aws:kms and gcs:cmek types)",
    )

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")


@dataclass(init=False)
class StorageLocalConfig(BaseConfig):
    """Local filesystem storage configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    root_dir: str = Field(
        default=storage_const.DEFAULT_LOCAL_ROOT_DIR,
        description="Root directory for file storage",
    )
    base_url: str = Field(
        default=storage_const.DEFAULT_LOCAL_BASE_URL,
        description="Base URL for file access",
    )


@dataclass(init=False)
class StorageS3Config(BaseConfig):
    """Configuration for AWS S3 storage."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    bucket: str = Field(..., description="S3 bucket name")
    region: str = Field(..., description="AWS region")
    access_key: SecretStr | None = Field(None, description="AWS access key")
    secret_key: SecretStr | None = Field(None, description="AWS secret key")
    endpoint_url: str | None = Field(
        None,
        description="Custom endpoint URL (for MinIO, etc.)",
    )
    public_url: str | None = Field(
        None,
        description="Custom public URL for serving files (e.g., Cloudflare R2 custom domain).",
    )
    encryption: EncryptionConfig = Field(
        default_factory=EncryptionConfig,
        description="Server-side encryption settings",
    )


@dataclass(init=False)
class StorageGCSConfig(BaseConfig):
    """Configuration for Google Cloud Storage."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    bucket: str = Field(..., description="GCS bucket name")
    project_id: str = Field(..., description="Google Cloud project ID")
    credentials_path: str | None = Field(
        None,
        description="Path to service account credentials",
    )
    encryption: EncryptionConfig = Field(
        default_factory=EncryptionConfig,
        description="Server-side encryption settings",
    )


@dataclass(init=False)
class StorageAzureConfig(BaseConfig):
    """Configuration for Azure Blob Storage."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    account_name: str = Field(..., description="Azure storage account name")
    account_key: SecretStr = Field(..., description="Azure storage account key")
    container: str = Field(..., description="Blob container name")


@dataclass(init=False)
class StorageR2Config(BaseConfig):
    """Configuration for Cloudflare R2 storage (S3-compatible).

    R2 uses the same API surface as AWS S3 but requires an explicit
    ``endpoint_url`` and credentials — IAM roles are not available.

    Args:
        bucket: R2 bucket name
        access_key: R2 access key ID
        secret_key: R2 secret access key
        endpoint_url: R2 S3-compatible API endpoint URL (for signing operations)
        public_url: Optional custom domain URL for public file access.
            When set, get_url() returns this instead of endpoint_url.
            Example: https://cdn.example.com
        region: R2 region (default: auto)
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    bucket: str = Field(..., description="R2 bucket name")
    access_key: SecretStr = Field(..., description="R2 access key ID (required)")
    secret_key: SecretStr = Field(..., description="R2 secret access key (required)")
    endpoint_url: str = Field(
        ..., description="R2 S3-compatible endpoint URL (required)"
    )
    public_url: str | None = Field(
        default=None,
        description="Optional custom domain URL for public file access",
    )
    region: str = Field(
        default="auto",
        description="R2 region name (default: auto)",
    )


@dataclass(init=False)
class StorageMemoryConfig(BaseConfig):
    """Configuration for in-memory storage (testing)."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")


@dataclass(init=False)
class StorageOperationConfig(BaseConfig):
    """Configuration for storage service operations."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    max_file_size_mb: int = Field(
        default=storage_const.DEFAULT_MAX_FILE_SIZE_MB,
        description="Maximum file size in MB",
    )
    allowed_mime_types: list[str] = Field(
        default_factory=lambda: [
            "image/jpeg",
            "image/png",
            "image/gif",
            "image/webp",
        ],
        description=(
            "Allowed MIME types for upload validation. "
            "Defaults to a safe set of common image types: "
            "['image/jpeg', 'image/png', 'image/gif', 'image/webp']. "
            "An empty list ([]) blocks ALL uploads — every file will be rejected. "
            "Use ['*/*'] to allow any MIME type (permissive; not recommended for "
            "production without additional validation)."
        ),
    )


@dataclass(init=False)
class NamedStorageConfig(DomainModel):
    """Configuration for a single named storage backend.

    Used in StorageConfig.backends to declare multiple blob stores
    that the framework registers as named DI bindings.

    Example:
        backends:
          - name: primary
            driver: s3
            primary: true
            s3:
              bucket: my-app-primary
              region: us-east-1
          - name: avatars
            driver: s3
            s3:
              bucket: my-app-avatars
              region: us-east-1
          - name: local
            driver: local
            local:
              root_dir: ./storage/public

    Args:
        name: Unique backend identifier. Used as the Named() DI key.
        primary: Whether this is the primary backend. Primary backends
            also receive the unnamed BlobStoreProtocol binding.
        driver: Storage driver name. One of: local, s3, gcs, azure, r2, memory.
        local: Local filesystem driver config (when driver='local').
        s3: AWS S3 driver config (when driver='s3').
        gcs: Google Cloud Storage config (when driver='gcs').
        azure: Azure Blob Storage config (when driver='azure').
        r2: Cloudflare R2 config (when driver='r2').
        memory: In-memory storage config (when driver='memory').
    """

    name: str = Field(..., description="Unique backend name used as the Named() DI key")
    primary: bool = Field(
        default=False,
        description="Also register under unnamed BlobStoreProtocol binding",
    )
    driver: Literal["local", "s3", "gcs", "azure", "r2", "memory"] = Field(
        default="local", description="Storage driver name"
    )
    local: StorageLocalConfig | None = Field(default=None)
    s3: StorageS3Config | None = Field(default=None)
    gcs: StorageGCSConfig | None = Field(default=None)
    azure: StorageAzureConfig | None = Field(default=None)
    r2: StorageR2Config | None = Field(default=None)
    memory: StorageMemoryConfig | None = Field(default=None)


@dataclass(init=False)
class StorageConfig(BaseConfig):
    """Hierarchical root configuration for Quadkit Storage.

    Attributes:
        name: Configuration name (default: "storage")
        enabled: Whether storage module is enabled
        default_driver: Default storage driver (local, s3, gcs, azure, memory)
        drivers: Driver-specific configurations
        service: Storage operation settings

    Example::

        # From environment variables (``QK_STORAGE__*``)
        config = StorageConfig()

        # Explicit values
        config = StorageConfig(default_driver="s3", drivers={"s3": StorageS3Config(...)})

    """

    config_section: ClassVar[str] = "storage"

    model_config = cast(
        "ConfigDict",
        {
            "env_prefix": storage_const.ENV_PREFIX,
            "env_nested_delimiter": storage_const.ENV_NESTED_DELIMITER,
            "extra": "ignore",
        },
    )

    name: str = "storage"
    enabled: bool = True
    default_driver: Literal["local", "s3", "gcs", "azure", "memory", "r2"] = Field(
        default=storage_const.DEFAULT_DRIVER,  # type: ignore[arg-type]
        description="Default storage driver to use",
    )
    health_check_timeout: float = Field(
        default=5.0,
        description="Timeout in seconds for the startup health check in StorageProvider.boot()",
        gt=0,
    )
    drivers: dict[
        str,
        StorageLocalConfig
        | StorageS3Config
        | StorageGCSConfig
        | StorageAzureConfig
        | StorageMemoryConfig
        | StorageR2Config,
    ] = Field(default_factory=dict, description="Driver-specific configurations")
    service: StorageOperationConfig = Field(
        default_factory=StorageOperationConfig,
        description="Operation settings",
    )
    backends: list[NamedStorageConfig] = Field(
        default_factory=list,
        description=(
            "Named storage backends for multi-store support. "
            "When non-empty, the provider registers each backend under "
            "Annotated[BlobStoreProtocol, Named(entry.name)]. "
            "The first entry (or the one with primary=True) also receives "
            "the unnamed BlobStoreProtocol binding for backward compatibility."
        ),
    )
    env: Environment | None = Field(default=None, description="Deployment environment")

    @classmethod
    def from_named(cls, entry: NamedStorageConfig) -> StorageConfig:
        """Build a single-backend StorageConfig from a NamedStorageConfig entry.

        Used internally by StorageProvider to create per-backend configs
        from a multi-backend declaration. The resulting config has the
        driver-specific config placed in the drivers dict under the driver
        type key, so the existing DriverRegistry can consume it unchanged.

        Args:
            entry: The named backend entry to materialise.

        Returns:
            A StorageConfig configured for the single named backend.
        """
        drivers: dict[str, Any] = {}
        driver_cfg = getattr(entry, entry.driver, None)
        if driver_cfg is not None:
            drivers[entry.driver] = driver_cfg

        return cls(
            enabled=True,
            default_driver=entry.driver,
            drivers=drivers,
            backends=[],  # prevent recursion
            service=StorageOperationConfig(),
        )

    @model_validator(mode="after")
    def validate_production_security(self) -> StorageConfig:
        """Block insecure storage configurations in production.

        This validator fires when the environment is set to ``production``.
        It rejects known-weak placeholder credentials (``"change-me"``,
        ``"password"``, etc.) in S3 and Azure driver configs, raising
        ``ValueError`` immediately so the application fails fast at startup
        rather than leaking credentials at request time.
        """
        if Environment.from_env() == Environment.PRODUCTION:
            insecure_defaults = storage_const.INSECURE_SECRET_VALUES

            for name, driver in self.drivers.items():
                if isinstance(driver, StorageS3Config):
                    if (
                        driver.secret_key
                        and driver.secret_key.get_secret_value().lower()
                        in insecure_defaults
                    ):
                        raise ValueError(
                            f"CRITICAL SECURITY ERROR: Insecure AWS S3 secret_key detected"
                            f" in PRODUCTION for driver '{name}'.\n"
                            "You MUST set a secure secret key via"
                            " QK_STORAGE__DRIVERS__<name>__SECRET_KEY.",
                        )
                elif isinstance(driver, StorageAzureConfig) and (
                    driver.account_key.get_secret_value().lower() in insecure_defaults
                ):
                    raise ValueError(
                        f"CRITICAL SECURITY ERROR: Insecure Azure account_key detected"
                        f" in PRODUCTION for driver '{name}'.\n"
                        "You MUST set a secure account key via"
                        " QK_STORAGE__DRIVERS__<name>__ACCOUNT_KEY.",
                    )

        return self


__all__ = [
    "EncryptionConfig",
    "NamedStorageConfig",
    "StorageAzureConfig",
    "StorageConfig",
    "StorageGCSConfig",
    "StorageLocalConfig",
    "StorageMemoryConfig",
    "StorageOperationConfig",
    "StorageR2Config",
    "StorageS3Config",
]
