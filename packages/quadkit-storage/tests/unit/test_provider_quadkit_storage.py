"""Unit tests for storage provider"""

from unittest.mock import MagicMock

import pytest

from quadkit.contracts import BlobStoreProtocol
from quadkit.di import Container
from quadkit.storage.config import StorageLocalConfig, StorageConfig
from quadkit.storage.backends.local import LocalDriver
from quadkit.storage.backends.memory import MemoryDriver
from quadkit.storage.di.provider import StorageProvider


class TestStorageProvider:
    """Test the StorageProvider class"""

    def test_storage_provider_creation(self):
        """Test storage provider creation"""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config)
        assert provider.config == config

    @pytest.mark.asyncio
    async def test_register_memory_driver(self):
        """Test registering memory driver"""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config)

        mock_container = MagicMock()
        await provider.register(mock_container)

        # register() calls singleton twice: once for DriverRegistry, once for BlobStoreProtocol
        assert mock_container.singleton.call_count == 2
        # The last call must bind the concrete driver to BlobStoreProtocol
        last_call_args = mock_container.singleton.call_args
        assert last_call_args[0][0] == BlobStoreProtocol
        assert isinstance(last_call_args[0][1], MemoryDriver)

    @pytest.mark.asyncio
    async def test_register_local_driver(self):
        """Test registering local driver"""
        local_config = StorageLocalConfig(
            root_dir="/tmp/storage", base_url="http://localhost:8000/storage",
        )
        config = StorageConfig(default_driver="local", drivers={"local": local_config})
        provider = StorageProvider(config)

        mock_container = MagicMock()
        await provider.register(mock_container)

        # register() calls singleton twice: once for DriverRegistry, once for BlobStoreProtocol
        assert mock_container.singleton.call_count == 2
        # The last call must bind the concrete driver to BlobStoreProtocol
        last_call_args = mock_container.singleton.call_args
        assert last_call_args[0][0] == BlobStoreProtocol
        assert isinstance(last_call_args[0][1], LocalDriver)

    @pytest.mark.asyncio
    async def test_register_unknown_driver(self):
        """Test registering unknown driver raises error"""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config)
        # Manually set an unknown driver to test the error case
        provider.config.default_driver = "unknown"

        mock_container = MagicMock()

        with pytest.raises(ValueError) as exc_info:
            await provider.register(mock_container)

        assert "Unknown storage driver" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_register_s3_driver_requires_bucket(self):
        """Test registering S3 driver requires bucket configuration"""
        pytest.importorskip("aiobotocore")

        config = StorageConfig(default_driver="s3")
        provider = StorageProvider(config)

        mock_container = MagicMock()

        # Should fail because bucket is required but not provided
        with pytest.raises((TypeError, ValueError)) as exc_info:
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_register_gcs_driver_requires_optional_dep(self):
        """Test that GCS driver raises ImportError without gcloud-aio-storage installed"""
        config = StorageConfig(default_driver="gcs")
        provider = StorageProvider(config)

        mock_container = MagicMock()

        with pytest.raises((ImportError, ValueError)):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_register_azure_driver_requires_optional_dep(self):
        """Test that Azure driver raises ImportError without azure-storage-blob installed"""
        config = StorageConfig(default_driver="azure")
        provider = StorageProvider(config)

        mock_container = MagicMock()

        with pytest.raises((ImportError, ValueError)):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_startup(self):
        """Test startup method"""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config)

        mock_app = MagicMock()
        await provider.boot(mock_app)
        # Startup should not raise any errors

    @pytest.mark.asyncio
    async def test_shutdown(self):
        """Test shutdown method"""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config)

        mock_app = MagicMock()
        await provider.shutdown()
        # Shutdown should not raise any errors

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check method"""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config)

        result = await provider.health_check()
        assert result.status.value == "healthy"
        assert result.details["driver"] == "memory"

    # ------------------------------------------------------------------
    # Config validation tests (P0: fail fast with clear error messages)
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_validate_s3_missing_config_block(self) -> None:
        """S3 driver raises ValueError with actionable message when drivers.s3 missing."""
        config = StorageConfig(default_driver="s3")
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"'drivers\.s3' configuration block"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_s3_missing_bucket(self) -> None:
        """S3 driver raises ValueError with actionable message when bucket is missing."""
        from quadkit.storage.config import StorageS3Config

        s3_cfg = MagicMock(spec=StorageS3Config)
        s3_cfg.bucket = None
        s3_cfg.region = "us-east-1"
        config = StorageConfig(default_driver="s3", drivers={"s3": s3_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.s3\.bucket"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_s3_missing_region(self) -> None:
        """S3 driver raises ValueError with actionable message when region is missing."""
        from quadkit.storage.config import StorageS3Config

        s3_cfg = MagicMock(spec=StorageS3Config)
        s3_cfg.bucket = "my-bucket"
        s3_cfg.region = None
        config = StorageConfig(default_driver="s3", drivers={"s3": s3_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.s3\.region"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_gcs_missing_config_block(self) -> None:
        """GCS driver raises ValueError with actionable message when drivers.gcs missing."""
        config = StorageConfig(default_driver="gcs")
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"'drivers\.gcs' configuration block"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_gcs_missing_bucket(self) -> None:
        """GCS driver raises ValueError when bucket missing."""
        gcs_cfg = MagicMock()
        gcs_cfg.bucket = None
        gcs_cfg.project_id = "my-project"
        config = StorageConfig(default_driver="gcs", drivers={"gcs": gcs_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.gcs\.bucket"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_gcs_missing_project_id(self) -> None:
        """GCS driver raises ValueError when project_id missing."""
        gcs_cfg = MagicMock()
        gcs_cfg.bucket = "my-bucket"
        gcs_cfg.project_id = None
        config = StorageConfig(default_driver="gcs", drivers={"gcs": gcs_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.gcs\.project_id"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_azure_missing_config_block(self) -> None:
        """Azure driver raises ValueError with actionable message when drivers.azure missing."""
        config = StorageConfig(default_driver="azure")
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"'drivers\.azure' configuration block"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_azure_missing_account_name(self) -> None:
        """Azure driver raises ValueError when account_name missing."""
        azure_cfg = MagicMock()
        azure_cfg.account_name = None
        azure_cfg.account_key = "key"
        azure_cfg.container = "mycontainer"
        config = StorageConfig(default_driver="azure", drivers={"azure": azure_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.azure\.account_name"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_azure_missing_account_key(self) -> None:
        """Azure driver raises ValueError when account_key missing."""
        azure_cfg = MagicMock()
        azure_cfg.account_name = "myaccount"
        azure_cfg.account_key = None
        azure_cfg.container = "mycontainer"
        config = StorageConfig(default_driver="azure", drivers={"azure": azure_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.azure\.account_key"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_azure_missing_container(self) -> None:
        """Azure driver raises ValueError when container missing."""
        azure_cfg = MagicMock()
        azure_cfg.account_name = "myaccount"
        azure_cfg.account_key = "key"
        azure_cfg.container = None
        config = StorageConfig(default_driver="azure", drivers={"azure": azure_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.azure\.container"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_local_and_memory_need_no_extra_config(self) -> None:
        """Local and memory drivers pass validation without extra driver config."""
        for driver_type in ("local", "memory"):
            config = StorageConfig(default_driver=driver_type)
            provider = StorageProvider(config)
            mock_container = MagicMock()
            # Should not raise — validation passes for these drivers
            await provider.register(mock_container)

    # --- R2 validation tests ------------------------------------------------

    @pytest.mark.asyncio
    async def test_validate_r2_missing_config_block(self) -> None:
        """R2 driver raises ValueError with actionable message when drivers.r2 missing."""
        config = StorageConfig(default_driver="r2")
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"'drivers\.r2' configuration block"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_r2_missing_bucket(self) -> None:
        """R2 driver raises ValueError when bucket missing."""
        r2_cfg = MagicMock()
        r2_cfg.bucket = None
        r2_cfg.access_key = "key"
        r2_cfg.secret_key = "secret"
        r2_cfg.endpoint_url = "https://account.r2.cloudflarestorage.com"
        config = StorageConfig(default_driver="r2", drivers={"r2": r2_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.r2\.bucket"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_r2_missing_access_key(self) -> None:
        """R2 driver raises ValueError when access_key missing."""
        r2_cfg = MagicMock()
        r2_cfg.bucket = "mybucket"
        r2_cfg.access_key = None
        r2_cfg.secret_key = "secret"
        r2_cfg.endpoint_url = "https://account.r2.cloudflarestorage.com"
        config = StorageConfig(default_driver="r2", drivers={"r2": r2_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.r2\.access_key"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_r2_missing_secret_key(self) -> None:
        """R2 driver raises ValueError when secret_key missing."""
        r2_cfg = MagicMock()
        r2_cfg.bucket = "mybucket"
        r2_cfg.access_key = "key"
        r2_cfg.secret_key = None
        r2_cfg.endpoint_url = "https://account.r2.cloudflarestorage.com"
        config = StorageConfig(default_driver="r2", drivers={"r2": r2_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.r2\.secret_key"):
            await provider.register(mock_container)

    @pytest.mark.asyncio
    async def test_validate_r2_missing_endpoint_url(self) -> None:
        """R2 driver raises ValueError when endpoint_url missing."""
        r2_cfg = MagicMock()
        r2_cfg.bucket = "mybucket"
        r2_cfg.access_key = "key"
        r2_cfg.secret_key = "secret"
        r2_cfg.endpoint_url = None
        config = StorageConfig(default_driver="r2", drivers={"r2": r2_cfg})
        provider = StorageProvider(config)
        mock_container = MagicMock()

        with pytest.raises(ValueError, match=r"drivers\.r2\.endpoint_url"):
            await provider.register(mock_container)
