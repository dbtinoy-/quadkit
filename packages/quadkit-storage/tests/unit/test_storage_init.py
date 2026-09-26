"""Tests for storage package __init__.py - lazy imports and exports."""

import pytest


class TestStoragePackage:
    """Tests for quadkit.storage package exports."""

    def test_version_accessible(self):
        """__version__ should be accessible."""
        from quadkit import storage
        assert storage.__version__ is not None
        assert isinstance(storage.__version__, str)

    def test_lazy_import_storage_config(self):
        """StorageConfig should be lazily imported."""
        from quadkit import storage
        config_cls = storage.StorageConfig
        assert config_cls is not None

    def test_lazy_import_storage_provider(self):
        """StorageProvider should be lazily imported."""
        from quadkit import storage
        provider_cls = storage.StorageProvider
        assert provider_cls is not None

    def test_lazy_import_blob_store_protocol(self):
        """BlobStoreProtocol should be lazily imported."""
        from quadkit import storage
        protocol_cls = storage.BlobStoreProtocol
        assert protocol_cls is not None

    def test_lazy_import_file_info(self):
        """FileInfo should be lazily imported."""
        from quadkit import storage
        file_info_cls = storage.FileInfo
        assert file_info_cls is not None

    def test_lazy_import_upload_options(self):
        """UploadOptions should be lazily imported."""
        from quadkit import storage
        upload_options_cls = storage.UploadOptions
        assert upload_options_cls is not None

    def test_lazy_import_local_driver(self):
        """LocalDriver should be lazily imported."""
        from quadkit import storage
        driver_cls = storage.LocalDriver
        assert driver_cls is not None

    def test_lazy_import_memory_driver(self):
        """MemoryDriver should be lazily imported."""
        from quadkit import storage
        driver_cls = storage.MemoryDriver
        assert driver_cls is not None

    def test_all_includes_all_exports(self):
        """__all__ should include all expected exports."""
        from quadkit import storage
        expected = [
            "BlobStoreProtocol",
            "FileInfo",
            "StorageConfig",
            "StorageProvider",
            "UploadOptions",
            "Uploadable",
            "LocalDriver",
            "MemoryDriver",
            "S3Driver",
            "GCSDriver",
            "AzureDriver",
            "__version__",
        ]
        for name in expected:
            assert name in storage.__all__, f"{name} not in __all__"

    def test_dir_includes_all_exports(self):
        """__dir__ should include all lazy imports and __version__."""
        from quadkit import storage
        dir_result = dir(storage)
        
        assert "__version__" in dir_result
        assert "StorageConfig" in dir_result
        assert "StorageProvider" in dir_result
        assert "BlobStoreProtocol" in dir_result
        assert "LocalDriver" in dir_result

    def test_invalid_attribute_raises(self):
        """Accessing non-existent attribute should raise AttributeError."""
        from quadkit import storage
        
        with pytest.raises(AttributeError) as exc_info:
            storage.NonExistentClass
        
        assert "has no attribute" in str(exc_info.value)
        assert "NonExistentClass" in str(exc_info.value)

    def test_multiple_access_same_lazy_import(self):
        """Multiple accesses should return the same class."""
        from quadkit import storage
        
        config1 = storage.StorageConfig
        config2 = storage.StorageConfig
        assert config1 is config2
