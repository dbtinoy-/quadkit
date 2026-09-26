"""Unit tests for atomic file upload"""

import asyncio
import hashlib
from pathlib import Path
import tempfile

import pytest

from quadkit.storage.backends.local import LocalDriver
from quadkit.storage.exceptions import StorageError
from quadkit.contracts.infra.storage import UploadOptions


class TestAtomicUpload:
    """Test atomic file upload behavior"""

    @pytest.fixture
    def temp_storage_dir(self):
        """Create temp directory for storage tests"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def driver(self, temp_storage_dir):
        """Create LocalDriver instance with temp directory"""
        return LocalDriver(root_dir=temp_storage_dir)

    @pytest.mark.asyncio
    async def test_successful_upload_creates_file(self, driver, temp_storage_dir):
        """Successful upload should create the target file"""
        data = b"test content"
        file_info = await driver.upload("test/file.txt", data)

        assert file_info.path == "test/file.txt"
        assert file_info.size == len(data)

        # Verify file exists
        full_path = Path(temp_storage_dir) / "test" / "file.txt"
        assert full_path.exists()
        assert full_path.read_bytes() == data

    @pytest.mark.asyncio
    async def test_upload_with_valid_checksum_succeeds(self, driver):
        """Upload with correct checksum should succeed"""
        data = b"test content with checksum"
        expected_checksum = hashlib.sha256(data).hexdigest()

        options = UploadOptions(metadata={"checksum": expected_checksum})

        file_info = await driver.upload("test/checksum.txt", data, options)
        assert file_info.path == "test/checksum.txt"

    @pytest.mark.asyncio
    async def test_upload_with_invalid_checksum_fails(self, driver, temp_storage_dir):
        """Upload with wrong checksum should fail and not leave partial file"""
        data = b"test content"
        wrong_checksum = "deadbeef" * 8  # Invalid SHA256

        options = UploadOptions(metadata={"checksum": wrong_checksum})

        with pytest.raises(StorageError) as exc_info:
            await driver.upload("test/bad_checksum.txt", data, options)

        # Error message should include expected and actual checksums
        msg = str(exc_info.value)
        expected_checksum = hashlib.sha256(data).hexdigest()
        assert wrong_checksum in msg
        assert expected_checksum in msg

        # Verify NO partial file exists
        full_path = Path(temp_storage_dir) / "test" / "bad_checksum.txt"
        assert not full_path.exists()

    @pytest.mark.asyncio
    async def test_upload_failure_leaves_no_partial_file(
        self, driver, temp_storage_dir,
    ):
        """Upload failure should not leave partial files"""

        # Create an async iterator that fails mid-stream
        async def failing_stream():
            yield b"chunk1"
            yield b"chunk2"
            raise RuntimeError("Simulated network error")

        with pytest.raises(StorageError):
            await driver.upload("test/failed.txt", failing_stream())

        # Verify NO file exists
        full_path = Path(temp_storage_dir) / "test" / "failed.txt"
        assert not full_path.exists()

        # Verify no temp files left behind
        temp_files = list(Path(temp_storage_dir).rglob(".upload_*.tmp"))
        assert len(temp_files) == 0

    @pytest.mark.asyncio
    async def test_upload_different_data_types(self, driver):
        """Test upload with bytes, str, and async iterator"""
        # Bytes
        await driver.upload("test/bytes.bin", b"binary data")

        # String
        await driver.upload("test/string.txt", "text data")

        # Async iterator
        async def data_stream():
            yield b"chunk1"
            yield b"chunk2"
            yield b"chunk3"

        await driver.upload("test/stream.bin", data_stream())

        # Verify all exist
        assert await driver.exists("test/bytes.bin")
        assert await driver.exists("test/string.txt")
        assert await driver.exists("test/stream.bin")

    @pytest.mark.asyncio
    async def test_no_temp_files_after_successful_upload(
        self, driver, temp_storage_dir,
    ):
        """No temp files should remain after successful upload"""
        await driver.upload("test/clean.txt", b"content")

        # Check for any remaining temp files
        temp_files = list(Path(temp_storage_dir).rglob(".upload_*.tmp"))
        assert len(temp_files) == 0

    @pytest.mark.asyncio
    async def test_concurrent_uploads_do_not_interfere(self, driver):
        """Multiple concurrent uploads should all succeed independently"""

        async def upload_file(i: int):
            data = f"file {i} content".encode()
            return await driver.upload(f"test/concurrent_{i}.txt", data)

        # Upload 10 files concurrently
        results = await asyncio.gather(*list(map(lambda i: upload_file(i), range(10))))

        assert len(results) == 10
        for i, file_info in enumerate(results):
            assert file_info.path == f"test/concurrent_{i}.txt"
            assert await driver.exists(f"test/concurrent_{i}.txt")
