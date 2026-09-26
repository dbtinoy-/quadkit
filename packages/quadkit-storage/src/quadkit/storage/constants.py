"""Constants for quadkit-storage."""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__: str = importlib.metadata.version("quadkit-storage")
except ImportError:
    __version__ = "0.0.0"

# -- Environment Variable Prefixes -------------------------------------------

ENV_PREFIX: str = "QK_STORAGE__"
ENV_NESTED_DELIMITER: str = "__"

# -- Default Configuration Values --------------------------------------------

DEFAULT_DRIVER: str = "local"
DEFAULT_LOCAL_ROOT_DIR: str = "./storage"
DEFAULT_LOCAL_BASE_URL: str = "http://localhost:8000/storage"
DEFAULT_MAX_FILE_SIZE_MB: int = 10

# -- Supported Drivers -------------------------------------------------------

DRIVER_LOCAL: str = "local"
DRIVER_S3: str = "s3"
DRIVER_GCS: str = "gcs"
DRIVER_AZURE: str = "azure"
DRIVER_MEMORY: str = "memory"
DRIVER_R2: str = "r2"

SUPPORTED_DRIVERS: tuple[str, ...] = (
    DRIVER_LOCAL,
    DRIVER_S3,
    DRIVER_GCS,
    DRIVER_AZURE,
    DRIVER_MEMORY,
    DRIVER_R2,
)

# -- Security ----------------------------------------------------------------

INSECURE_SECRET_VALUES: tuple[str, ...] = (
    "change-me",
    "password",
    "123456",
    "secret",
    "your-secret-key",
)

__all__ = [
    "DEFAULT_DRIVER",
    "DEFAULT_LOCAL_BASE_URL",
    "DEFAULT_LOCAL_ROOT_DIR",
    "DEFAULT_MAX_FILE_SIZE_MB",
    "DRIVER_AZURE",
    "DRIVER_GCS",
    "DRIVER_LOCAL",
    "DRIVER_MEMORY",
    "DRIVER_R2",
    "DRIVER_S3",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "INSECURE_SECRET_VALUES",
    "SUPPORTED_DRIVERS",
]
