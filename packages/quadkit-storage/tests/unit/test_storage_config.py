"""Unit tests for storage configuration models."""

from __future__ import annotations

import pytest

from quadkit.storage.config import (
    EncryptionConfig,
    NamedStorageConfig,
    StorageAzureConfig,
    StorageConfig,
    StorageGCSConfig,
    StorageLocalConfig,
    StorageMemoryConfig,
    StorageOperationConfig,
    StorageR2Config,
    StorageS3Config,
)


class TestEncryptionConfig:
    def test_defaults(self) -> None:
        config = EncryptionConfig()
        assert config.enabled is False
        assert config.type == "AES256"
        assert config.kms_key_id is None

    def test_with_kms(self) -> None:
        config = EncryptionConfig(enabled=True, type="aws:kms", kms_key_id="arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012")
        assert config.enabled is True
        assert config.type == "aws:kms"
        assert config.kms_key_id == "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"

    def test_with_gcs_cmek(self) -> None:
        config = EncryptionConfig(enabled=True, type="gcs:cmek", kms_key_id="my-key-ring")
        assert config.enabled is True
        assert config.type == "gcs:cmek"
        assert config.kms_key_id == "my-key-ring"


class TestStorageLocalConfig:
    def test_defaults(self) -> None:
        config = StorageLocalConfig()
        assert config.root_dir == "./storage"
        assert config.base_url == "http://localhost:8000/storage"


class TestStorageS3Config:
    def test_required_fields(self) -> None:
        config = StorageS3Config(bucket="test-bucket", region="us-east-1")
        assert config.bucket == "test-bucket"
        assert config.region == "us-east-1"

    def test_with_credentials(self) -> None:
        # Deliberately not AWS's canonical documentation example key: that
        # string matches the export's secret scanner, which blocks the whole
        # public tree over a value that was never a credential. The test is
        # about credentials round-tripping, not about the shape of a real
        # key ID -- and a comment naming the example would trip the same
        # scanner, so it is described rather than quoted.
        config = StorageS3Config(
            bucket="test-bucket",
            region="us-west-2",
            access_key="TEST-ACCESS-KEY-ID",
            secret_key="TEST-SECRET-ACCESS-KEY",
        )
        assert config.access_key is not None
        assert config.secret_key is not None

    def test_with_endpoint_for_minio(self) -> None:
        config = StorageS3Config(
            bucket="minio-bucket",
            region="us-east-1",
            endpoint_url="http://localhost:9000",
        )
        assert config.endpoint_url == "http://localhost:9000"


class TestStorageGCSConfig:
    def test_required_fields(self) -> None:
        config = StorageGCSConfig(bucket="test-bucket", project_id="my-project-123")
        assert config.bucket == "test-bucket"
        assert config.project_id == "my-project-123"

    def test_with_credentials_path(self) -> None:
        config = StorageGCSConfig(
            bucket="test-bucket",
            project_id="my-project-123",
            credentials_path="/path/to/credentials.json",
        )
        assert config.credentials_path == "/path/to/credentials.json"


class TestStorageAzureConfig:
    def test_required_fields(self) -> None:
        config = StorageAzureConfig(
            account_name="mystorageaccount",
            account_key="testkey123==",
            container="mycontainer",
        )
        assert config.account_name == "mystorageaccount"
        assert config.account_key.get_secret_value() == "testkey123=="
        assert config.container == "mycontainer"


class TestStorageR2Config:
    def test_required_fields(self) -> None:
        config = StorageR2Config(
            bucket="r2-bucket",
            access_key="test-access-key",
            secret_key="test-secret-key",
            endpoint_url="https://abc123.r2.cloudflarestorage.com",
        )
        assert config.bucket == "r2-bucket"
        assert config.access_key.get_secret_value() == "test-access-key"
        assert config.secret_key.get_secret_value() == "test-secret-key"
        assert config.endpoint_url == "https://abc123.r2.cloudflarestorage.com"
        assert config.region == "auto"

    def test_with_custom_region(self) -> None:
        config = StorageR2Config(
            bucket="r2-bucket",
            access_key="key",
            secret_key="secret",
            endpoint_url="https://abc123.r2.cloudflarestorage.com",
            region="ewr",
        )
        assert config.region == "ewr"


class TestStorageMemoryConfig:
    def test_empty(self) -> None:
        config = StorageMemoryConfig()
        assert config is not None


class TestStorageOperationConfig:
    def test_defaults(self) -> None:
        config = StorageOperationConfig()
        assert config.max_file_size_mb == 10
        assert config.allowed_mime_types == ["image/jpeg", "image/png", "image/gif", "image/webp"]

    def test_custom_allowed_types(self) -> None:
        config = StorageOperationConfig(allowed_mime_types=["application/pdf"])
        assert config.allowed_mime_types == ["application/pdf"]

    def test_empty_allowed_types_blocks_all(self) -> None:
        config = StorageOperationConfig(allowed_mime_types=[])
        assert config.allowed_mime_types == []


class TestNamedStorageConfig:
    def test_local_driver(self) -> None:
        config = NamedStorageConfig(
            name="local-files",
            driver="local",
            local=StorageLocalConfig(root_dir="/tmp/storage"),
        )
        assert config.name == "local-files"
        assert config.driver == "local"
        assert config.primary is False

    def test_s3_driver_as_primary(self) -> None:
        config = NamedStorageConfig(
            name="primary-s3",
            driver="s3",
            primary=True,
            s3=StorageS3Config(bucket="primary-bucket", region="us-east-1"),
        )
        assert config.name == "primary-s3"
        assert config.driver == "s3"
        assert config.primary is True

    def test_default_driver_is_local(self) -> None:
        config = NamedStorageConfig(name="default")
        assert config.driver == "local"


class TestStorageConfig:
    def test_defaults(self) -> None:
        config = StorageConfig()
        assert config.name == "storage"
        assert config.enabled is True
        assert config.default_driver == "local"
        assert config.health_check_timeout == 5.0
        assert config.drivers == {}
        assert config.backends == []

    def test_with_s3_driver(self) -> None:
        s3_config = StorageS3Config(bucket="test-bucket", region="us-east-1")
        config = StorageConfig(drivers={"s3": s3_config})
        assert config.drivers["s3"] == s3_config

    def test_from_named_local(self) -> None:
        named = NamedStorageConfig(
            name="local-files",
            driver="local",
            primary=True,
            local=StorageLocalConfig(root_dir="/custom/storage"),
        )
        config = StorageConfig.from_named(named)
        assert config.enabled is True
        assert config.default_driver == "local"
        assert config.drivers.get("local") is not None
        assert config.backends == []

    def test_from_named_s3(self) -> None:
        named = NamedStorageConfig(
            name="s3-files",
            driver="s3",
            s3=StorageS3Config(bucket="my-bucket", region="us-west-2"),
        )
        config = StorageConfig.from_named(named)
        assert config.enabled is True
        assert config.default_driver == "s3"
        assert config.drivers.get("s3") is not None

    @pytest.mark.parametrize("insecure_value", ["change-me", "password", "123456", "secret", "your-secret-key"])
    def test_validate_production_security_rejects_insecure_s3(self, insecure_value: str) -> None:
        import os

        original_env = os.environ.get("QK_ENV")
        try:
            os.environ["QK_ENV"] = "production"
            with pytest.raises(ValueError, match="CRITICAL SECURITY ERROR.*Insecure AWS S3 secret_key"):
                StorageConfig(
                    drivers={
                        "s3": StorageS3Config(
                            bucket="test-bucket",
                            region="us-east-1",
                            secret_key=insecure_value,
                        ),
                    },
                )
        finally:
            if original_env is not None:
                os.environ["QK_ENV"] = original_env
            else:
                os.environ.pop("QK_ENV", None)

    def test_validate_production_security_passes_in_dev(self) -> None:
        import os

        original_env = os.environ.get("QK_ENV")
        try:
            os.environ["QK_ENV"] = "development"
            config = StorageConfig(
                drivers={
                    "s3": StorageS3Config(
                        bucket="test-bucket",
                        region="us-east-1",
                        secret_key="change-me",
                    ),
                },
            )
            result = config.validate_production_security()
            assert result is config
        finally:
            if original_env is not None:
                os.environ["QK_ENV"] = original_env
            else:
                os.environ.pop("QK_ENV", None)