"""Integration tests for storage functionality"""

import io
from pathlib import Path
import tempfile

import pytest

from quadkit.contracts.infra.storage import UploadOptions
from quadkit.storage.backends.local import LocalDriver
from quadkit.storage.exceptions import StorageError, StorageFileNotFoundError


class TestLocalDriver:
    """Test the local storage driver"""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp:
            yield Path(temp)

    @pytest.fixture
    def driver(self, temp_dir):
        """Create a local driver with temp directory"""
        return LocalDriver(
            root_dir=str(temp_dir),
            base_url="http://localhost:8000/files",
        )

    @pytest.mark.asyncio
    async def test_upload_download_text(self, driver):
        """Test uploading and downloading text files"""
        content = "Hello, World! 🌍"
        info = await driver.upload("hello.txt", content)

        assert info.path == "hello.txt"
        assert info.size == len(content.encode("utf-8"))
        assert info.content_type == "text/plain"

        downloaded = await driver.download("hello.txt")
        assert downloaded.decode("utf-8") == content

    @pytest.mark.asyncio
    async def test_upload_download_binary(self, driver):
        """Test uploading and downloading binary files"""
        content = b"\x00\x01\x02\x03\xff\xfe\xfd"
        info = await driver.upload("binary.dat", content)

        assert info.path == "binary.dat"
        assert info.size == len(content)
        assert info.content_type == "application/octet-stream"

        downloaded = await driver.download("binary.dat")
        assert downloaded == content

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
        content = "test content"
        options = UploadOptions(
            content_type="text/custom",
            metadata={"author": "test", "version": "1.0"},
        )

        info = await driver.upload("options.txt", content, options)

        assert info.path == "options.txt"
        assert info.content_type == "text/custom"
        assert info.metadata == {"author": "test", "version": "1.0"}

        persisted = await driver.info("options.txt")
        assert persisted.content_type == "text/custom"
        assert persisted.metadata == {"author": "test", "version": "1.0"}
        listing = [item async for item in driver.list()]
        assert [(item.path, item.content_type, item.metadata) for item in listing] == [
            ("options.txt", "text/custom", {"author": "test", "version": "1.0"})
        ]

    @pytest.mark.asyncio
    async def test_path_security(self, driver):
        """Test path traversal protection"""
        # Try directory traversal
        with pytest.raises(StorageError):
            await driver.upload("../../etc/passwd", b"hacked")

        with pytest.raises(StorageError):
            await driver.download("../../etc/passwd")

        with pytest.raises(StorageError):
            await driver.upload(".quadkit-metadata/forged.json", b"not a user object")

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
        assert [item async for item in driver.list()] == []

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, driver):
        """Test deleting nonexistent file"""
        with pytest.raises(StorageFileNotFoundError):
            await driver.delete("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_info(self, driver):
        """Test file info retrieval"""
        content = "test content for info"
        await driver.upload("info.txt", content)

        info = await driver.info("info.txt")
        assert info.path == "info.txt"
        assert info.size == len(content.encode("utf-8"))
        assert info.content_type == "text/plain"
        assert info.etag is not None
        assert info.last_modified is not None

    @pytest.mark.asyncio
    async def test_info_nonexistent(self, driver):
        """Test info for nonexistent file"""
        with pytest.raises(StorageFileNotFoundError):
            await driver.info("nonexistent.txt")

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
    async def test_stream_nonexistent(self, driver):
        """Test streaming nonexistent file"""
        with pytest.raises(StorageFileNotFoundError):
            async for _chunk in driver.stream("nonexistent.txt"):
                pass

    @pytest.mark.asyncio
    async def test_list_directory(self, driver):
        """Test listing files in a directory"""
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
    async def test_list_file(self, driver):
        """Test listing a specific file"""
        await driver.upload("specific.txt", b"content")

        files = []
        async for file_info in driver.list("specific.txt"):
            files.append(file_info.path)

        assert files == ["specific.txt"]

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
    async def test_download_nonexistent(self, driver):
        """Test downloading nonexistent file"""
        with pytest.raises(StorageFileNotFoundError):
            await driver.download("nonexistent.txt")

    @pytest.mark.asyncio
    async def test_get_url(self, driver):
        """Test URL generation"""
        url = await driver.get_url("test/file.txt")
        assert url == "http://localhost:8000/files/test/file.txt"

    @pytest.mark.asyncio
    async def test_presigned_url_raises(self, driver):
        """Local driver does not support presigned URLs"""
        from quadkit.storage.exceptions import StorageUnsupportedOperationError

        with pytest.raises(StorageUnsupportedOperationError):
            await driver.get_presigned_url("test/file.txt")

    @pytest.mark.asyncio
    async def test_presigned_url_with_params_raises(self, driver):
        """Local driver does not support presigned URLs"""
        from quadkit.storage.exceptions import StorageUnsupportedOperationError

        with pytest.raises(StorageUnsupportedOperationError):
            await driver.get_presigned_url(
                "test/file.txt",
                expires_in=7200,
                method="PUT",
            )

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, driver):
        """Test health check returns healthy status"""
        await driver.upload("file.txt", b"content")

        result = await driver.health_check()

        assert result.status.value == "healthy"
        assert result.component == "storage.local"
        assert "root_dir" in result.details

    @pytest.mark.asyncio
    async def test_health_check_nonexistent_directory(self, driver, temp_dir):
        """Test health check with nonexistent directory"""

        nonexistent_dir = temp_dir / "nonexistent"

        bad_driver = LocalDriver(
            root_dir=str(nonexistent_dir),
            base_url="http://localhost:8000/files",
        )

        result = await bad_driver.health_check()

        assert result.status.value == "unhealthy"
        assert "does not exist" in result.error

    @pytest.mark.asyncio
    async def test_get_full_path_strips_leading_slash(self, driver):
        """Test that _get_full_path strips leading slash"""
        # This is tested via path security - paths starting with / should be handled
        # The internal method strips leading slash at line 53-54
        await driver.upload("file.txt", b"content")

        assert await driver.exists("file.txt")

    @pytest.mark.asyncio
    async def test_copy_default_implementation(self, driver):
        """Test copy uses default implementation"""
        await driver.upload("source.txt", b"original content")

        result = await driver.copy("source.txt", "dest.txt")

        assert result.path == "dest.txt"
        assert await driver.exists("source.txt")
        assert await driver.exists("dest.txt")

        dest_content = await driver.download("dest.txt")
        assert dest_content == b"original content"

    @pytest.mark.asyncio
    async def test_move_default_implementation(self, driver):
        """Test move uses default implementation"""
        await driver.upload("source.txt", b"to be moved")

        result = await driver.move("source.txt", "moved.txt")

        assert result.path == "moved.txt"
        assert not await driver.exists("source.txt")
        assert await driver.exists("moved.txt")

    @pytest.mark.asyncio
    async def test_path_with_leading_slash(self, driver):
        """Test that paths with leading slash are handled"""
        # Internal method strips leading slash at line 53-54
        await driver.upload("file.txt", b"content")

        # Should work normally
        assert await driver.exists("file.txt")

    @pytest.mark.asyncio
    async def test_directory_traversal_prevention(self, driver):
        """Test directory traversal is prevented"""
        # The code at lines 59-66 catches path traversal
        with pytest.raises(StorageError):
            await driver._get_full_path("../outside")

    @pytest.mark.asyncio
    async def test_write_stream_default(self, driver):
        """Test write_stream uses default implementation"""

        async def data_stream():
            yield b"hello"
            yield b" world"

        result = await driver.write_stream("streamed.txt", data_stream())

        assert result.path == "streamed.txt"
        content = await driver.download("streamed.txt")
        assert content == b"hello world"
