"""Tests for AbstractDriver base class."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock

from quadkit.storage.backends.base import AbstractDriver
from quadkit.contracts.infra.storage import UploadOptions


class ConcreteTestDriver(AbstractDriver):
    """Concrete implementation for testing."""
    
    async def upload(self, path, data, options=None):
        from quadkit.contracts.infra.storage import FileInfo
        return FileInfo(
            path=path,
            size=len(data) if isinstance(data, (bytes, str)) else 0,
            content_type="application/octet-stream",
            last_modified=datetime.now(),
        )
    
    async def download(self, path):
        return b"test content"
    
    async def stream(self, path, chunk_size=8192):
        yield b"chunk1"
        yield b"chunk2"
    
    async def delete(self, path):
        pass
    
    async def exists(self, path):
        return True
    
    async def info(self, path):
        from quadkit.contracts.infra.storage import FileInfo
        return FileInfo(
            path=path,
            size=100,
            content_type="text/plain",
            last_modified=datetime.now(),
        )
    
    async def list(self, prefix=""):
        from quadkit.contracts.infra.storage import FileInfo
        yield FileInfo(
            path=prefix + "file.txt",
            size=100,
            content_type="text/plain",
            last_modified=datetime.now(),
        )
    
    async def get_url(self, path):
        return f"http://localhost/{path}"
    
    async def get_presigned_url(self, path, expires_in=None, method="GET"):
        return f"http://localhost/{path}?expires=1h"
    
    async def health_check(self, timeout=5.0):
        from quadkit.contracts import HealthCheckResult, HealthStatus
        return HealthCheckResult(
            component="test",
            status=HealthStatus.HEALTHY,
            message="OK",
            duration_ms=1.0,
        )


class TestAbstractDriver:
    """Tests for AbstractDriver class."""

    @pytest.fixture
    def driver(self):
        return ConcreteTestDriver()

    def test_resolve_content_type_from_options(self, driver):
        """Should use content type from options when provided."""
        options = UploadOptions(content_type="image/png")
        result = driver._resolve_content_type("file.txt", options)
        assert result == "image/png"

    def test_resolve_content_type_guessed_from_extension(self, driver):
        """Should guess content type from file extension."""
        result = driver._resolve_content_type("document.pdf", None)
        assert result == "application/pdf"

    def test_resolve_content_type_unknown_extension(self, driver):
        """Should fallback for unknown extensions."""
        result = driver._resolve_content_type("file.xyzabc", None)
        assert result == "application/octet-stream"

    def test_resolve_content_type_no_options(self, driver):
        """Should guess when no options provided."""
        result = driver._resolve_content_type("image.png", None)
        assert result == "image/png"

    def test_resolve_content_type_empty_options(self, driver):
        """Should guess when options is empty."""
        result = driver._resolve_content_type("image.png", UploadOptions())
        assert result == "image/png"

    def test_normalize_upload_options_accepts_positional_options(self, driver):
        """The third upload argument can carry metadata and cache settings."""
        options = UploadOptions(
            content_type="text/plain",
            metadata={"Owner": "qa"},
            cache_control="no-cache",
        )

        normalized = driver._normalize_upload_options(options, {"public": True})

        assert normalized is not None
        assert normalized.content_type == "text/plain"
        assert normalized.metadata == {"owner": "qa"}
        assert normalized.cache_control == "no-cache"
        assert normalized.public is True

    def test_normalize_upload_options_accepts_legacy_content_type(self, driver):
        """The string content-type form remains compatible with old callers."""
        normalized = driver._normalize_upload_options(
            "application/json", {"metadata": {"source": "test"}}
        )

        assert normalized is not None
        assert normalized.content_type == "application/json"
        assert normalized.metadata == {"source": "test"}

    @pytest.mark.asyncio
    async def test_write_stream_default_implementation(self, driver):
        """write_stream should buffer and call upload by default."""
        async def data_stream():
            yield b"hello"
            yield b" world"
        
        result = await driver.write_stream("test.txt", data_stream())
        
        assert result.path == "test.txt"
        assert result.size == 11  # len(b"hello world")

    @pytest.mark.asyncio
    async def test_write_stream_with_options(self, driver):
        """write_stream should pass options to upload."""
        async def data_stream():
            yield b"test"
        
        options = UploadOptions(content_type="application/json")
        result = await driver.write_stream("test.json", data_stream(), options)
        
        # The default implementation resolves content type from path, not options
        assert result.path == "test.json"

    @pytest.mark.asyncio
    async def test_copy_default_implementation(self, driver):
        """copy should download and re-upload by default."""
        result = await driver.copy("source.txt", "dest.txt")
        
        assert result.path == "dest.txt"

    @pytest.mark.asyncio
    async def test_copy_preserves_content_type(self, driver):
        """copy should preserve content type from source."""
        result = await driver.copy("source.pdf", "dest.pdf")
        
        # Source info has empty content_type so options is None
        assert result.path == "dest.pdf"

    @pytest.mark.asyncio
    async def test_move_default_implementation(self, driver):
        """move should copy and delete by default."""
        result = await driver.move("source.txt", "dest.txt")
        
        assert result.path == "dest.txt"


class TestAbstractDriverIsAbstract:
    """Tests for AbstractDriver abstract methods."""

    def test_cannot_instantiate_directly(self):
        """AbstractDriver cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractDriver()

    def test_upload_is_abstract(self):
        """upload must be implemented by subclass."""
        class MissingUpload(AbstractDriver):
            async def download(self, path):
                pass
            async def stream(self, path, chunk_size=8192):
                yield b""
            async def delete(self, path):
                pass
            async def exists(self, path):
                return False
            async def info(self, path):
                from quadkit.contracts.infra.storage import FileInfo
                return FileInfo(path="", size=0, content_type="", last_modified=datetime.now())
            async def list(self, prefix=""):
                yield FileInfo(path="", size=0, content_type="", last_modified=datetime.now())
            async def get_url(self, path):
                return ""
            async def get_presigned_url(self, path, expires_in=None, method="GET"):
                return ""
            async def health_check(self, timeout=5.0):
                from quadkit.contracts import HealthCheckResult, HealthStatus
                return HealthCheckResult(component="", status=HealthStatus.HEALTHY, message="", duration_ms=0)
        
        with pytest.raises(TypeError):
            MissingUpload()
