"""Unit tests for storage drivers"""

import io
from datetime import timedelta

import pytest

from quadkit.storage.backends.memory import MemoryDriver
from quadkit.contracts.infra.storage import UploadOptions
from quadkit.storage.exceptions import StorageFileNotFoundError, StorageUnsupportedOperationError


class TestMemoryDriver:
    """Test the memory storage driver"""

    @pytest.fixture
    def driver(self):
        return MemoryDriver()

    @pytest.mark.asyncio
    async def test_upload_and_download(self, driver):
        """Test basic upload and download"""
        # Upload
        info = await driver.upload("test.txt", b"Hello World")

        assert info.path == "test.txt"
        assert info.size == 11
        assert info.content_type == "application/octet-stream"

        # Download
        content = await driver.download("test.txt")
        assert content == b"Hello World"

    @pytest.mark.asyncio
    async def test_upload_binary_io(self, driver):
        """Test uploading from BinaryIO"""
        content = b"BinaryIO content"
        bio = io.BytesIO(content)
        info = await driver.upload("binary_io.dat", bio)

        assert info.path == "binary_io.dat"
        assert info.size == len(content)

        downloaded = await driver.download("binary_io.dat")
        assert downloaded == content

    @pytest.mark.asyncio
    async def test_upload_async_iterator(self, driver):
        """Test uploading from AsyncIterator"""

        async def content_generator():
            yield b"chunk1"
            yield b"chunk2"
            yield b"chunk3"

        info = await driver.upload("async_iter.dat", content_generator())

        assert info.path == "async_iter.dat"
        assert info.size == 18  # "chunk1chunk2chunk3"

        downloaded = await driver.download("async_iter.dat")
        assert downloaded == b"chunk1chunk2chunk3"

    @pytest.mark.asyncio
    async def test_upload_with_options(self, driver):
        """Test uploading with custom options"""
        content = b"test content"
        options = UploadOptions(
            content_type="text/custom", metadata={"author": "test", "version": "1.0"},
        )

        info = await driver.upload("options.txt", content, options)

        assert info.path == "options.txt"
        assert info.content_type == "text/custom"
        assert info.metadata == {"author": "test", "version": "1.0"}

    @pytest.mark.asyncio
    async def test_exists(self, driver):
        """Test file existence checking"""
        assert not await driver.exists("nonexistent.txt")

        await driver.upload("exists.txt", b"content")
        assert await driver.exists("exists.txt")

    @pytest.mark.asyncio
    async def test_delete(self, driver):
        """Test file deletion"""
        await driver.upload("delete_me.txt", b"content")
        assert await driver.exists("delete_me.txt")

        await driver.delete("delete_me.txt")
        assert not await driver.exists("delete_me.txt")

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, driver):
        """Test deleting nonexistent file"""
        with pytest.raises(StorageFileNotFoundError):
            await driver.delete("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_info(self, driver):
        """Test file info retrieval"""
        await driver.upload("info.txt", b"test content")

        info = await driver.info("info.txt")
        assert info.path == "info.txt"
        assert info.size == 12
        assert info.content_type == "application/octet-stream"

    @pytest.mark.asyncio
    async def test_info_nonexistent(self, driver):
        """Test info for nonexistent file"""
        with pytest.raises(StorageFileNotFoundError):
            await driver.info("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_download_nonexistent(self, driver):
        """Test downloading nonexistent file"""
        with pytest.raises(StorageFileNotFoundError):
            await driver.download("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_stream_nonexistent(self, driver):
        """Test streaming nonexistent file"""
        with pytest.raises(StorageFileNotFoundError):
            async for chunk in driver.stream("nonexistent.txt"):
                pass

    @pytest.mark.asyncio
    async def test_stream(self, driver):
        """Test streaming download"""
        content = b"0123456789" * 100  # 1KB of data
        await driver.upload("stream.txt", content)

        chunks = []
        async for chunk in driver.stream("stream.txt", chunk_size=100):
            chunks.append(chunk)

        assert len(chunks) > 1  # Should be split into multiple chunks
        assert b"".join(chunks) == content

    @pytest.mark.asyncio
    async def test_list(self, driver):
        """Test file listing"""
        await driver.upload("dir/file1.txt", b"content1")
        await driver.upload("dir/file2.txt", b"content2")
        await driver.upload("other.txt", b"content3")

        files = []
        async for file_info in driver.list("dir/"):
            files.append(file_info.path)

        assert "dir/file1.txt" in files
        assert "dir/file2.txt" in files
        assert "other.txt" not in files

    @pytest.mark.asyncio
    async def test_list_all(self, driver):
        """Test listing all files"""
        await driver.upload("file1.txt", b"content1")
        await driver.upload("file2.txt", b"content2")

        files = []
        async for file_info in driver.list():
            files.append(file_info.path)

        assert "file1.txt" in files
        assert "file2.txt" in files

    @pytest.mark.asyncio
    async def test_get_url(self, driver):
        """Test URL generation"""
        url = await driver.get_url("test/file.txt")
        assert url == "memory://test/file.txt"

    @pytest.mark.asyncio
    async def test_upload_presigned_url(self, driver):
        """Test that get_presigned_url raises an unsupported operation error."""
        with pytest.raises(StorageUnsupportedOperationError):
            await driver.get_presigned_url("test/file.txt", expires_in=timedelta(hours=2), method="PUT")

    @pytest.mark.asyncio
    async def test_upload_unsupported_data_type(self, driver):
        """Test uploading unsupported data type raises error"""
        with pytest.raises(ValueError) as exc_info:
            await driver.upload("test.txt", 123)  # Integer is not supported

        assert "Unsupported data type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_string_data(self, driver):
        """Test uploading string data is encoded to bytes"""
        info = await driver.upload("text.txt", "Hello World")
        
        assert info.path == "text.txt"
        assert info.size == 11
        downloaded = await driver.download("text.txt")
        assert downloaded == b"Hello World"

    @pytest.mark.asyncio
    async def test_upload_binary_io_returning_string(self, driver):
        """Test uploading from BinaryIO that returns string"""
        class StringIO:
            def __init__(self, data):
                self._data = data
            def read(self):
                return self._data
        
        info = await driver.upload("string_io.txt", StringIO("string data"))
        
        assert info.size == 11
        downloaded = await driver.download("string_io.txt")
        assert downloaded == b"string data"

    @pytest.mark.asyncio
    async def test_upload_binary_io_unsupported_return_type(self, driver):
        """Test uploading from BinaryIO with unsupported return type"""
        class UnsupportedIO:
            def read(self):
                return 12345  # Integer is not supported
        
        with pytest.raises(ValueError) as exc_info:
            await driver.upload("unsupported.txt", UnsupportedIO())
        
        assert "Unsupported read() return type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_upload_async_iterator_yielding_strings(self, driver):
        """Test uploading from async iterator yielding strings"""
        async def string_generator():
            yield "part1"
            yield "part2"
        
        info = await driver.upload("strings.txt", string_generator())
        
        assert info.size == 10
        downloaded = await driver.download("strings.txt")
        assert downloaded == b"part1part2"

    @pytest.mark.asyncio
    async def test_health_check(self, driver):
        """Test health check returns healthy status"""
        await driver.upload("file.txt", b"content")
        
        result = await driver.health_check()
        
        assert result.status.value == "healthy"
        assert result.component == "storage.memory"
        assert "file_count" in result.details
        assert result.details["file_count"] == 1
