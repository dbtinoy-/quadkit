"""Unit tests for StorageProvider - comprehensive edge cases and error handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from quadkit.contracts import HealthCheckResult, HealthStatus
from quadkit.storage.config import StorageConfig
from quadkit.storage.di.provider import (
    StorageProvider,
    _validate_s3,
    _validate_gcs,
    _validate_azure,
    _validate_r2,
)


class TestStorageProviderAttributes:
    """Tests for StorageProvider class attributes."""

    def test_name_attribute(self):
        """Provider has correct name."""
        provider = StorageProvider(config=StorageConfig(default_driver="memory"))
        assert provider.name == "storage"

    def test_priority_is_infrastructure(self):
        """Provider has infrastructure priority."""
        from quadkit.contracts import ProviderPriority

        provider = StorageProvider(config=StorageConfig(default_driver="memory"))
        assert provider.priority == ProviderPriority.INFRASTRUCTURE

    def test_config_key_attribute(self):
        """Provider has correct config_key."""
        provider = StorageProvider(config=StorageConfig(default_driver="memory"))
        assert provider.config_key == "storage"

    def test_config_model_attribute(self):
        """Provider has config_model set."""
        provider = StorageProvider(config=StorageConfig(default_driver="memory"))
        assert provider.config_model == StorageConfig


class TestProviderFromConfig:
    """Tests for from_config classmethod."""

    def test_from_config_creates_provider(self):
        """from_config should create provider with config."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider.from_config(config)
        assert provider.config == config

    def test_from_config_returns_self_type(self):
        """from_config should return Self type."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider.from_config(config)
        assert type(provider).__name__ == "StorageProvider"


class TestValidateS3Function:
    """Tests for _validate_s3 function."""

    def test_s3_missing_config_block(self):
        """Should raise when drivers.s3 is missing."""
        with pytest.raises(ValueError, match=r"'drivers\.s3' configuration block"):
            _validate_s3("s3", {})

    def test_s3_missing_bucket(self):
        """Should raise when bucket is missing."""
        cfg = MagicMock()
        cfg.bucket = None
        cfg.region = "us-east-1"
        with pytest.raises(ValueError, match=r"drivers\.s3\.bucket"):
            _validate_s3("s3", {"s3": cfg})

    def test_s3_missing_region(self):
        """Should raise when region is missing."""
        cfg = MagicMock()
        cfg.bucket = "my-bucket"
        cfg.region = None
        with pytest.raises(ValueError, match=r"drivers\.s3\.region"):
            _validate_s3("s3", {"s3": cfg})

    def test_s3_valid_config_passes(self):
        """Should pass with valid config."""
        cfg = MagicMock()
        cfg.bucket = "my-bucket"
        cfg.region = "us-east-1"
        _validate_s3("s3", {"s3": cfg})


class TestValidateGCSFunction:
    """Tests for _validate_gcs function."""

    def test_gcs_missing_config_block(self):
        """Should raise when drivers.gcs is missing."""
        with pytest.raises(ValueError, match=r"'drivers\.gcs' configuration block"):
            _validate_gcs("gcs", {})

    def test_gcs_missing_bucket(self):
        """Should raise when bucket is missing."""
        cfg = MagicMock()
        cfg.bucket = None
        cfg.project_id = "my-project"
        with pytest.raises(ValueError, match=r"drivers\.gcs\.bucket"):
            _validate_gcs("gcs", {"gcs": cfg})

    def test_gcs_missing_project_id(self):
        """Should raise when project_id is missing."""
        cfg = MagicMock()
        cfg.bucket = "my-bucket"
        cfg.project_id = None
        with pytest.raises(ValueError, match=r"drivers\.gcs\.project_id"):
            _validate_gcs("gcs", {"gcs": cfg})

    def test_gcs_valid_config_passes(self):
        """Should pass with valid config."""
        cfg = MagicMock()
        cfg.bucket = "my-bucket"
        cfg.project_id = "my-project"
        _validate_gcs("gcs", {"gcs": cfg})


class TestValidateAzureFunction:
    """Tests for _validate_azure function."""

    def test_azure_missing_config_block(self):
        """Should raise when drivers.azure is missing."""
        with pytest.raises(ValueError, match=r"'drivers\.azure' configuration block"):
            _validate_azure("azure", {})

    def test_azure_missing_account_name(self):
        """Should raise when account_name is missing."""
        cfg = MagicMock()
        cfg.account_name = None
        cfg.account_key = "key"
        cfg.container = "mycontainer"
        with pytest.raises(ValueError, match=r"drivers\.azure\.account_name"):
            _validate_azure("azure", {"azure": cfg})

    def test_azure_missing_account_key(self):
        """Should raise when account_key is missing."""
        cfg = MagicMock()
        cfg.account_name = "myaccount"
        cfg.account_key = None
        cfg.container = "mycontainer"
        with pytest.raises(ValueError, match=r"drivers\.azure\.account_key"):
            _validate_azure("azure", {"azure": cfg})

    def test_azure_missing_container(self):
        """Should raise when container is missing."""
        cfg = MagicMock()
        cfg.account_name = "myaccount"
        cfg.account_key = "key"
        cfg.container = None
        with pytest.raises(ValueError, match=r"drivers\.azure\.container"):
            _validate_azure("azure", {"azure": cfg})

    def test_azure_valid_config_passes(self):
        """Should pass with valid config."""
        cfg = MagicMock()
        cfg.account_name = "myaccount"
        cfg.account_key = "key"
        cfg.container = "mycontainer"
        _validate_azure("azure", {"azure": cfg})


class TestValidateR2Function:
    """Tests for _validate_r2 function."""

    def test_r2_missing_config_block(self):
        """Should raise when drivers.r2 is missing."""
        with pytest.raises(ValueError, match=r"'drivers\.r2' configuration block"):
            _validate_r2("r2", {})

    def test_r2_missing_bucket(self):
        """Should raise when bucket is missing."""
        cfg = MagicMock()
        cfg.bucket = None
        cfg.access_key = "key"
        cfg.secret_key = "secret"
        cfg.endpoint_url = "https://example.com"
        with pytest.raises(ValueError, match=r"drivers\.r2\.bucket"):
            _validate_r2("r2", {"r2": cfg})

    def test_r2_missing_access_key(self):
        """Should raise when access_key is missing."""
        cfg = MagicMock()
        cfg.bucket = "mybucket"
        cfg.access_key = None
        cfg.secret_key = "secret"
        cfg.endpoint_url = "https://example.com"
        with pytest.raises(ValueError, match=r"drivers\.r2\.access_key"):
            _validate_r2("r2", {"r2": cfg})

    def test_r2_missing_secret_key(self):
        """Should raise when secret_key is missing."""
        cfg = MagicMock()
        cfg.bucket = "mybucket"
        cfg.access_key = "key"
        cfg.secret_key = None
        cfg.endpoint_url = "https://example.com"
        with pytest.raises(ValueError, match=r"drivers\.r2\.secret_key"):
            _validate_r2("r2", {"r2": cfg})

    def test_r2_missing_endpoint_url(self):
        """Should raise when endpoint_url is missing."""
        cfg = MagicMock()
        cfg.bucket = "mybucket"
        cfg.access_key = "key"
        cfg.secret_key = "secret"
        cfg.endpoint_url = None
        with pytest.raises(ValueError, match=r"drivers\.r2\.endpoint_url"):
            _validate_r2("r2", {"r2": cfg})

    def test_r2_valid_config_passes(self):
        """Should pass with valid config."""
        cfg = MagicMock()
        cfg.bucket = "mybucket"
        cfg.access_key = "key"
        cfg.secret_key = "secret"
        cfg.endpoint_url = "https://example.com"
        _validate_r2("r2", {"r2": cfg})


class TestProviderBootEdgeCases:
    """Tests for boot method edge cases."""

    @pytest.mark.asyncio
    async def test_boot_with_no_drivers_no_driver_attribute(self):
        """boot should handle missing _driver attribute gracefully."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)
        container = MagicMock()
        await provider.boot(container)

    @pytest.mark.asyncio
    async def test_boot_single_driver_with_health_check(self):
        """boot should call health_check on single driver."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)

        mock_driver = MagicMock()
        mock_driver.health_check = AsyncMock(
            return_value=HealthCheckResult(
                component="storage", status=HealthStatus.HEALTHY, duration_ms=1
            )
        )
        provider._driver = mock_driver

        container = MagicMock()
        await provider.boot(container)
        mock_driver.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_boot_single_driver_with_exists_no_health_check(self):
        """boot should use exists when health_check not available."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)

        mock_driver = MagicMock(spec=["exists"])
        mock_driver.exists = AsyncMock(return_value=True)
        provider._driver = mock_driver

        container = MagicMock()
        await provider.boot(container)
        mock_driver.exists.assert_called_once()


class TestProviderHealthCheckEdgeCases:
    """Tests for health_check method edge cases."""

    @pytest.mark.asyncio
    async def test_health_check_no_drivers_no_driver(self):
        """health_check should return healthy when no _driver."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)
        result = await provider.health_check()
        assert result.status == HealthStatus.HEALTHY
        assert result.details["driver"] == "memory"

    @pytest.mark.asyncio
    async def test_health_check_with_driver_no_health_check_method(self):
        """health_check should handle driver without health_check."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)

        mock_driver = MagicMock()
        del mock_driver.health_check
        provider._driver = mock_driver

        result = await provider.health_check()
        assert result.status == HealthStatus.HEALTHY


class TestProviderShutdownEdgeCases:
    """Tests for shutdown method edge cases."""

    @pytest.mark.asyncio
    async def test_shutdown_with_no_drivers_no_driver(self):
        """shutdown should handle missing _driver attribute."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)
        await provider.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_driver_with_sync_close(self):
        """shutdown should handle sync close method."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)

        mock_driver = MagicMock()
        mock_driver.close = MagicMock()
        provider._driver = mock_driver

        await provider.shutdown()
        mock_driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_driver_with_async_close(self):
        """shutdown should handle async close method."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)

        mock_driver = MagicMock()
        mock_driver.close = AsyncMock()
        provider._driver = mock_driver

        await provider.shutdown()
        mock_driver.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_ignores_close_errors(self):
        """shutdown should ignore close errors."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)

        mock_driver = MagicMock()
        mock_driver.close = MagicMock(side_effect=OSError("test error"))
        provider._driver = mock_driver

        await provider.shutdown()


class TestProviderValidationDirect:
    """Tests for direct validation method calls."""

    def test_validate_driver_config_local_passes(self):
        """Local driver should pass without extra validation."""
        config = StorageConfig(default_driver="local")
        provider = StorageProvider(config=config)
        provider._validate_driver_config(config)

    def test_validate_driver_config_memory_passes(self):
        """Memory driver should pass without extra validation."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)
        provider._validate_driver_config(config)


class TestProviderBootErrors:
    """Tests for boot error handling."""

    @pytest.mark.asyncio
    async def test_boot_health_check_timeout(self):
        """boot should raise on health check timeout."""
        config = StorageConfig(default_driver="memory")
        config.health_check_timeout = 0.001
        provider = StorageProvider(config=config)

        async def slow_health():
            await asyncio.sleep(10)
            return HealthCheckResult(
                component="storage", status=HealthStatus.HEALTHY, duration_ms=1
            )

        import asyncio

        mock_driver = MagicMock()
        mock_driver.health_check = slow_health
        provider._driver = mock_driver

        container = MagicMock()
        with pytest.raises(RuntimeError, match="timed out"):
            await provider.boot(container)

    @pytest.mark.asyncio
    async def test_boot_health_check_unhealthy(self):
        """boot should raise when health check returns unhealthy."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)

        mock_driver = MagicMock()
        mock_driver.health_check = AsyncMock(
            return_value=HealthCheckResult(
                component="storage",
                status=HealthStatus.UNHEALTHY,
                error="Connection failed",
                duration_ms=1,
            )
        )
        provider._driver = mock_driver

        container = MagicMock()
        with pytest.raises(RuntimeError, match="health check failed"):
            await provider.boot(container)

    @pytest.mark.asyncio
    async def test_boot_exists_fails(self):
        """boot should raise when exists check fails."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)

        mock_driver = MagicMock(spec=["exists"])
        mock_driver.exists = AsyncMock(side_effect=RuntimeError("DB down"))
        provider._driver = mock_driver

        container = MagicMock()
        with pytest.raises(RuntimeError, match="health check failed"):
            await provider.boot(container)


from quadkit.storage import constants as storage_const


class TestProviderDriverTypeConstants:
    """Tests for driver type constants."""

    def test_driver_memory_constant(self):
        """DRIVER_MEMORY should be 'memory'."""
        assert storage_const.DRIVER_MEMORY == "memory"

    def test_driver_local_constant(self):
        """DRIVER_LOCAL should be 'local'."""
        assert storage_const.DRIVER_LOCAL == "local"

    def test_driver_s3_constant(self):
        """DRIVER_S3 should be 's3'."""
        assert storage_const.DRIVER_S3 == "s3"

    def test_driver_gcs_constant(self):
        """DRIVER_GCS should be 'gcs'."""
        assert storage_const.DRIVER_GCS == "gcs"

    def test_driver_azure_constant(self):
        """DRIVER_AZURE should be 'azure'."""
        assert storage_const.DRIVER_AZURE == "azure"

    def test_driver_r2_constant(self):
        """DRIVER_R2 should be 'r2'."""
        assert storage_const.DRIVER_R2 == "r2"


import asyncio


class TestProviderConfigProperty:
    """Tests for config property."""

    def test_config_property_returns_config(self):
        """config property should return the stored config."""
        config = StorageConfig(default_driver="memory")
        provider = StorageProvider(config=config)
        assert provider.config == config

    def test_config_property_is_none_when_not_set(self):
        """config property should return None when not set."""
        provider = StorageProvider()
        assert provider.config is None


class TestProviderRegisterResolvesConfig:
    """Tests for register resolving config from container."""

    @pytest.mark.asyncio
    async def test_register_resolves_config_from_container(self):
        """register should resolve config from container when not provided."""
        provider = StorageProvider()
        mock_container = MagicMock()

        mock_config_loader = MagicMock()
        mock_config = StorageConfig(default_driver="memory")
        mock_config_loader.get_section = MagicMock(return_value=mock_config)
        mock_container.resolve = AsyncMock(return_value=mock_config_loader)

        with patch("quadkit.storage.config.StorageConfig", StorageConfig):
            await provider.register(mock_container)

        assert provider.config == mock_config


import asyncio