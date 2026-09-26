"""Tests for storage constants."""

import pytest
from quadkit.storage.constants import (
    ENV_PREFIX,
    ENV_NESTED_DELIMITER,
    DEFAULT_DRIVER,
    DEFAULT_LOCAL_ROOT_DIR,
    DEFAULT_LOCAL_BASE_URL,
    DEFAULT_MAX_FILE_SIZE_MB,
    DRIVER_LOCAL,
    DRIVER_S3,
    DRIVER_GCS,
    DRIVER_AZURE,
    DRIVER_MEMORY,
    DRIVER_R2,
    SUPPORTED_DRIVERS,
    INSECURE_SECRET_VALUES,
)


class TestStorageEnvConstants:
    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_STORAGE__"

    def test_env_nested_delimiter(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"


class TestStorageDefaults:
    def test_default_driver(self) -> None:
        assert DEFAULT_DRIVER == "local"

    def test_default_local_root_dir(self) -> None:
        assert DEFAULT_LOCAL_ROOT_DIR == "./storage"

    def test_default_local_base_url(self) -> None:
        assert DEFAULT_LOCAL_BASE_URL == "http://localhost:8000/storage"

    def test_default_max_file_size_mb(self) -> None:
        assert DEFAULT_MAX_FILE_SIZE_MB == 10


class TestSupportedDrivers:
    def test_local(self) -> None:
        assert DRIVER_LOCAL == "local"

    def test_s3(self) -> None:
        assert DRIVER_S3 == "s3"

    def test_gcs(self) -> None:
        assert DRIVER_GCS == "gcs"

    def test_azure(self) -> None:
        assert DRIVER_AZURE == "azure"

    def test_memory(self) -> None:
        assert DRIVER_MEMORY == "memory"

    def test_r2(self) -> None:
        assert DRIVER_R2 == "r2"

    def test_supported_drivers_tuple(self) -> None:
        assert isinstance(SUPPORTED_DRIVERS, tuple)
        assert DRIVER_LOCAL in SUPPORTED_DRIVERS
        assert DRIVER_S3 in SUPPORTED_DRIVERS


class TestInsecureSecretValues:
    def test_contains_common_insecure(self) -> None:
        assert "change-me" in INSECURE_SECRET_VALUES
        assert "password" in INSECURE_SECRET_VALUES
        assert "secret" in INSECURE_SECRET_VALUES
