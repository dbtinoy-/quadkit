"""Integration tests for quadkit-storage package lifecycle."""

from __future__ import annotations

import pytest

from quadkit.storage.config import StorageConfig
from quadkit.storage.di.provider import StorageProvider


class TestStorageProviderIntegration:
    """Integration tests for StorageProvider basic functionality."""

    @pytest.mark.integration
    def test_provider_initialization_default(self):
        """Test StorageProvider initialization with default config."""
        provider = StorageProvider()
        assert provider.name == "storage"

    @pytest.mark.integration
    def test_provider_initialization_with_config(self):
        """Test StorageProvider initialization with custom config."""
        config = StorageConfig()
        provider = StorageProvider(config=config)
        assert provider.name == "storage"

    @pytest.mark.integration
    def test_provider_has_required_attributes(self):
        """Test provider has required attributes."""
        provider = StorageProvider()
        assert hasattr(provider, "name")

    @pytest.mark.integration
    def test_provider_priority(self):
        """Test provider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority
        provider = StorageProvider()
        assert provider.priority == ProviderPriority.INFRASTRUCTURE


class TestStorageConfigIntegration:
    """Integration tests for StorageConfig."""

    @pytest.mark.integration
    def test_config_creation(self):
        """Test StorageConfig can be created."""
        config = StorageConfig()
        assert config is not None

    @pytest.mark.integration
    def test_config_model_dump(self):
        """Test StorageConfig model can be serialized."""
        config = StorageConfig()
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)

    @pytest.mark.integration
    def test_config_has_backend(self):
        """Test StorageConfig has backend field."""
        config = StorageConfig(backend="local")
        assert config.backend == "local"

    @pytest.mark.integration
    def test_config_has_base_url(self):
        """Test StorageConfig has base_url field."""
        config = StorageConfig(base_url="http://localhost:9000")
        assert config.base_url == "http://localhost:9000"


class TestStorageModuleIntegration:
    """Integration tests for StorageModule."""

    @pytest.mark.integration
    def test_storage_module_import(self):
        """Test StorageModule can be imported."""
        from quadkit.storage.module import StorageModule
        assert StorageModule is not None


class TestStorageBackendsIntegration:
    """Integration tests for storage backends."""

    @pytest.mark.integration
    def test_local_driver_import(self):
        """Test LocalDriver can be imported."""
        from quadkit.storage.backends.local import LocalDriver
        assert LocalDriver is not None

    @pytest.mark.integration
    def test_s3_driver_import(self):
        """Test S3Driver can be imported."""
        from quadkit.storage.backends.s3 import S3Driver
        assert S3Driver is not None

    @pytest.mark.integration
    def test_gcs_driver_import(self):
        """Test GCSDriver can be imported."""
        from quadkit.storage.backends.gcs import GCSDriver
        assert GCSDriver is not None


class TestStorageProtocolsIntegration:
    """Integration tests for storage protocols."""

    @pytest.mark.integration
    def test_storage_driver_protocol_import(self):
        """Test StorageDriverProtocol can be imported."""
        from quadkit.contracts.infra.storage import StorageDriverProtocol
        assert StorageDriverProtocol is not None


class TestStorageExceptionsIntegration:
    """Integration tests for storage exceptions."""

    @pytest.mark.integration
    def test_storage_error_import(self):
        """Test StorageError can be imported."""
        from quadkit.storage.exceptions import StorageError
        assert StorageError is not None

    @pytest.mark.integration
    def test_storage_file_not_found_error_import(self):
        """Test StorageFileNotFoundError can be imported."""
        from quadkit.storage.exceptions import StorageFileNotFoundError
        assert StorageFileNotFoundError is not None