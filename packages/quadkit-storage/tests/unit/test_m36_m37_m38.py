"""Tests for M36 (chunk integrity), M37 (timedelta presigned URL), M38 (EncryptionConfig)."""

from __future__ import annotations

from datetime import timedelta

import pytest

from quadkit.storage.config import EncryptionConfig, StorageS3Config, StorageGCSConfig


# ---------------------------------------------------------------------------
# M38 — EncryptionConfig
# ---------------------------------------------------------------------------


class TestEncryptionConfig:
    def test_defaults_to_disabled(self) -> None:
        enc = EncryptionConfig()
        assert enc.enabled is False
        assert enc.type == "AES256"
        assert enc.kms_key_id is None

    def test_aes256_encryption(self) -> None:
        enc = EncryptionConfig(enabled=True)
        assert enc.enabled is True
        assert enc.type == "AES256"

    def test_kms_encryption(self) -> None:
        enc = EncryptionConfig(
            enabled=True, type="aws:kms", kms_key_id="arn:aws:kms:us-east-1:123:key/abc"
        )
        assert enc.type == "aws:kms"
        assert enc.kms_key_id == "arn:aws:kms:us-east-1:123:key/abc"

    def test_gcs_cmek_encryption(self) -> None:
        enc = EncryptionConfig(
            enabled=True,
            type="gcs:cmek",
            kms_key_id="projects/my-proj/locations/global/keyRings/kr/cryptoKeys/ck",
        )
        assert enc.type == "gcs:cmek"

    def test_storage_s3_config_includes_encryption(self) -> None:
        config = StorageS3Config(bucket="my-bucket", region="us-east-1")
        assert hasattr(config, "encryption")
        assert isinstance(config.encryption, EncryptionConfig)

    def test_storage_gcs_config_includes_encryption(self) -> None:
        config = StorageGCSConfig(bucket="my-bucket", project_id="my-project")
        assert hasattr(config, "encryption")
        assert isinstance(config.encryption, EncryptionConfig)


# ---------------------------------------------------------------------------
# M38 — S3Driver._build_sse_params() (without real aiobotocore)
# ---------------------------------------------------------------------------


class TestS3DriverBuildSseParams:
    """Test _build_sse_params without instantiating a real S3 client."""

    def _make_driver(self, encryption: EncryptionConfig):
        """Create a minimal S3Driver-like object with the encryption helper."""
        # We patch the __init__ to avoid the aiobotocore import requirement
        import types
        from quadkit.storage.backends import s3 as s3_mod

        obj = types.SimpleNamespace()
        obj.encryption = encryption
        # Bind the method from S3Driver class
        obj._build_sse_params = s3_mod.S3Driver._build_sse_params.__get__(obj)
        return obj

    def test_sse_disabled_returns_empty_dict(self) -> None:
        driver = self._make_driver(EncryptionConfig(enabled=False))
        assert driver._build_sse_params() == {}

    def test_sse_aes256_returns_correct_params(self) -> None:
        driver = self._make_driver(EncryptionConfig(enabled=True, type="AES256"))
        params = driver._build_sse_params()
        assert params == {"ServerSideEncryption": "AES256"}

    def test_sse_kms_without_key_id(self) -> None:
        driver = self._make_driver(EncryptionConfig(enabled=True, type="aws:kms"))
        params = driver._build_sse_params()
        assert params["ServerSideEncryption"] == "aws:kms"
        assert "SSEKMSKeyId" not in params

    def test_sse_kms_with_key_id(self) -> None:
        driver = self._make_driver(
            EncryptionConfig(
                enabled=True,
                type="aws:kms",
                kms_key_id="arn:aws:kms:us-east-1:123:key/abc",
            )
        )
        params = driver._build_sse_params()
        assert params["ServerSideEncryption"] == "aws:kms"
        assert params["SSEKMSKeyId"] == "arn:aws:kms:us-east-1:123:key/abc"


# ---------------------------------------------------------------------------
# M37 — timedelta for get_presigned_url (both drivers raise unsupported)
# ---------------------------------------------------------------------------


class TestPresignedUrlTimedelta:
    @pytest.mark.asyncio
    async def test_local_driver_accepts_timedelta_and_raises(self, tmp_path) -> None:
        from quadkit.storage.backends.local import LocalDriver
        from quadkit.storage.exceptions import StorageUnsupportedOperationError

        driver = LocalDriver(root_dir=str(tmp_path), base_url="http://localhost")
        with pytest.raises(StorageUnsupportedOperationError):
            await driver.get_presigned_url(
                "some/file.txt", expires_in=timedelta(minutes=5)
            )

    @pytest.mark.asyncio
    async def test_memory_driver_accepts_timedelta_and_raises(self) -> None:
        from quadkit.storage.backends.memory import MemoryDriver
        from quadkit.storage.exceptions import StorageUnsupportedOperationError

        driver = MemoryDriver()
        with pytest.raises(StorageUnsupportedOperationError):
            await driver.get_presigned_url(
                "some/file.txt", expires_in=timedelta(hours=24)
            )

    @pytest.mark.asyncio
    async def test_local_driver_default_expiry_raises(self, tmp_path) -> None:
        from quadkit.storage.backends.local import LocalDriver
        from quadkit.storage.exceptions import StorageUnsupportedOperationError

        driver = LocalDriver(root_dir=str(tmp_path), base_url="http://localhost")
        with pytest.raises(StorageUnsupportedOperationError):
            await driver.get_presigned_url("some/file.txt")
