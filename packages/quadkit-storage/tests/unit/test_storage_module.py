"""Tests for storage module."""

import pytest
from quadkit.storage import StorageModule
from quadkit.di.module import DynamicModule


class TestStorageModule:
    def test_storage_module_exists(self) -> None:
        assert StorageModule is not None

    def test_configure_exports_blob_store(self) -> None:
        from quadkit.contracts import BlobStoreProtocol

        result = StorageModule.configure(None)
        assert BlobStoreProtocol in result.exports

    def test_configure_with_config_type_check(self) -> None:
        with pytest.raises(TypeError, match="must be StorageConfig"):
            StorageModule.configure("invalid")

    def test_configure_returns_dynamic_module(self) -> None:
        result = StorageModule.configure()
        assert isinstance(result, DynamicModule)

    def test_configure_with_storage_config(self) -> None:
        from quadkit.storage.config import StorageConfig

        config = StorageConfig(default_driver="memory")
        result = StorageModule.configure(config)
        
        assert result.module == StorageModule
        assert len(result.providers) >= 1

    def test_configure_with_none_creates_valid_module(self) -> None:
        result = StorageModule.configure(None)
        
        assert result.module == StorageModule
        assert result.exports is not None

    def test_configure_with_dict_raises(self) -> None:
        with pytest.raises(TypeError) as exc_info:
            StorageModule.configure({"default_driver": "memory"})
        
        assert "must be StorageConfig" in str(exc_info.value)

    def test_configure_with_integer_raises(self) -> None:
        with pytest.raises(TypeError) as exc_info:
            StorageModule.configure(123)
        
        assert "must be StorageConfig" in str(exc_info.value)

    def test_module_has_configure_classmethod(self) -> None:
        assert hasattr(StorageModule, 'configure')
        assert callable(StorageModule.configure)
