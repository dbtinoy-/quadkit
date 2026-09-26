"""Tests for storage drivers __init__.py module."""

import pytest


class TestDriversInit:
    """Tests for drivers package exports."""

    def test_abstract_driver_importable(self):
        """AbstractDriver should be importable."""
        from quadkit.storage.backends import AbstractDriver
        assert AbstractDriver is not None

    def test_local_driver_importable(self):
        """LocalDriver should be importable."""
        from quadkit.storage.backends import LocalDriver
        assert LocalDriver is not None

    def test_memory_driver_importable(self):
        """MemoryDriver should be importable."""
        from quadkit.storage.backends import MemoryDriver
        assert MemoryDriver is not None

    def test_all_exports_core_drivers(self):
        """__all__ should include core drivers."""
        from quadkit.storage.backends import __all__
        
        assert "AbstractDriver" in __all__
        assert "LocalDriver" in __all__
        assert "MemoryDriver" in __all__

    def test_s3_driver_in_all_if_available(self):
        """S3Driver should be in __all__ if available."""
        from quadkit.storage.backends import S3Driver, __all__
        
        # Should either be real class or stub
        assert "S3Driver" in __all__
        
        # Check class name
        assert S3Driver.__name__ == "S3Driver"

    def test_gcs_driver_in_all_if_available(self):
        """GCSDriver should be in __all__ if available."""
        from quadkit.storage.backends import GCSDriver, __all__
        
        assert "GCSDriver" in __all__
        assert GCSDriver.__name__ == "GCSDriver"

    def test_azure_driver_in_all_if_available(self):
        """AzureDriver should be in __all__ if available."""
        from quadkit.storage.backends import AzureDriver, __all__
        
        assert "AzureDriver" in __all__
        assert AzureDriver.__name__ == "AzureDriver"


class TestUnavailableDrivers:
    """Tests for driver stubs (if any are unavailable)."""

    def test_driver_class_names(self):
        """All drivers should have correct class names."""
        from quadkit.storage.backends import (
            AbstractDriver,
            LocalDriver,
            MemoryDriver,
            S3Driver,
            GCSDriver,
            AzureDriver,
        )
        
        assert AbstractDriver.__name__ == "AbstractDriver"
        assert LocalDriver.__name__ == "LocalDriver"
        assert MemoryDriver.__name__ == "MemoryDriver"
        assert S3Driver.__name__ == "S3Driver"
        assert GCSDriver.__name__ == "GCSDriver"
        assert AzureDriver.__name__ == "AzureDriver"


class TestMakeUnavailableClass:
    """Tests for _make_unavailable_class function."""

    def test_make_unavailable_class_creates_stub(self):
        """Should create a stub class that raises ImportError."""
        from quadkit.storage.backends import _make_unavailable_class
        
        StubClass = _make_unavailable_class("TestDriver", "pip install test-driver")
        
        assert StubClass.__name__ == "TestDriver"
        assert StubClass.__qualname__ == "TestDriver"

    def test_unavailable_class_raises_on_init(self):
        """Unavailable class should raise ImportError on instantiation."""
        from quadkit.storage.backends import _make_unavailable_class
        
        StubClass = _make_unavailable_class("TestDriver", "pip install test-driver")
        
        with pytest.raises(ImportError) as exc_info:
            StubClass()
        
        assert "TestDriver" in str(exc_info.value)
        assert "pip install test-driver" in str(exc_info.value)

    def test_unavailable_class_with_args(self):
        """Unavailable class should show args in error message."""
        from quadkit.storage.backends import _make_unavailable_class
        
        StubClass = _make_unavailable_class("CustomDriver", "pip install custom")
        
        with pytest.raises(ImportError):
            StubClass("arg1", kwarg1="value")
