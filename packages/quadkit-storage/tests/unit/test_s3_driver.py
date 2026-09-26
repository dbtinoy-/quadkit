"""Unit tests for S3 storage driver"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest

# Skip all tests if aiobotocore is not available
pytest.importorskip("aiobotocore")

from quadkit.storage.backends.s3 import S3Driver
from quadkit.storage.exceptions import StorageError, StorageFileNotFoundError


class TestS3Driver:
    """Test S3 storage driver with multipart upload"""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client"""
        client = AsyncMock()

        # Mock responses
        client.put_object.return_value = {"ETag": '"test-etag"'}
        client.create_multipart_upload.return_value = {"UploadId": "test-upload-id"}
        client.upload_part.return_value = {"ETag": '"part-etag"'}
        client.complete_multipart_upload.return_value = {"ETag": '"multipart-etag"'}

        return client

    @pytest.fixture
    def driver(self, mock_s3_client):
        """Create S3 driver with mock client"""
        with patch("aiobotocore.session.get_session") as mock_session:
            mock_session.return_value.create_client.return_value = mock_s3_client
            driver = S3Driver(bucket="test-bucket")
            driver.s3_client = mock_s3_client  # Override the client
            return driver

    @pytest.mark.asyncio
    async def test_upload_small_file_single_part(self, driver, mock_s3_client):
        """Test uploading small file uses single put_object"""
        data = b"small file content"
        file_info = await driver.upload("test/small.txt", data)

        # Should use put_object, not multipart
        mock_s3_client.put_object.assert_called_once()
        mock_s3_client.create_multipart_upload.assert_not_called()

        assert file_info.path == "test/small.txt"
        assert file_info.size == len(data)

    @pytest.mark.asyncio
    async def test_upload_large_file_multipart(self, driver, mock_s3_client):
        """Test uploading large file uses multipart upload"""
        # Create data larger than threshold (5MB)
        large_data = b"x" * (6 * 1024 * 1024)  # 6MB

        file_info = await driver.upload("test/large.bin", large_data)

        # Should use multipart upload
        mock_s3_client.create_multipart_upload.assert_called_once()
        mock_s3_client.upload_part.assert_called()  # Should be called multiple times
        mock_s3_client.complete_multipart_upload.assert_called_once()
        mock_s3_client.put_object.assert_not_called()

        assert file_info.path == "test/large.bin"
        assert file_info.size == len(large_data)

    @pytest.mark.asyncio
    async def test_upload_multipart_with_async_iterator(self, driver, mock_s3_client):
        """Test multipart upload with async iterator"""

        async def data_stream():
            for i in range(3):
                yield f"chunk {i}".encode() * (2 * 1024 * 1024)  # 2MB chunks

        file_info = await driver.upload("test/stream.bin", data_stream())

        # Should use multipart upload
        mock_s3_client.create_multipart_upload.assert_called_once()
        assert mock_s3_client.upload_part.call_count == 3  # 3 chunks
        mock_s3_client.complete_multipart_upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_multipart_upload_failure_aborts(self, driver, mock_s3_client):
        """Test multipart upload failure properly aborts upload"""
        mock_s3_client.upload_part.side_effect = Exception("Upload failed")

        large_data = b"x" * (6 * 1024 * 1024)  # 6MB

        with pytest.raises(StorageError):
            await driver.upload("test/fail.bin", large_data)

        # Should abort the multipart upload
        mock_s3_client.abort_multipart_upload.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_file(self, driver, mock_s3_client):
        """Test downloading file from S3"""
        mock_response = {"Body": AsyncMock()}
        mock_response["Body"].read.return_value = b"file content"
        mock_s3_client.get_object.return_value = mock_response

        data = await driver.download("test/file.txt")

        assert data == b"file content"
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/file.txt",
        )

    @pytest.mark.asyncio
    async def test_download_nonexistent_file(self, driver, mock_s3_client):
        """Test downloading nonexistent file raises StorageFileNotFoundError"""
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "NoSuchKey"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        with pytest.raises(StorageFileNotFoundError):
            await driver.download("test/missing.txt")

    @pytest.mark.asyncio
    async def test_exists_file(self, driver, mock_s3_client):
        """Test checking if file exists"""
        mock_s3_client.head_object.return_value = {"ContentLength": 100}

        exists = await driver.exists("test/file.txt")
        assert exists

        mock_s3_client.head_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/file.txt",
        )

    @pytest.mark.asyncio
    async def test_exists_file_not_found(self, driver, mock_s3_client):
        """Test checking if nonexistent file exists"""
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "NotFound"}}
        mock_s3_client.head_object.side_effect = ClientError(
            error_response, "HeadObject",
        )

        exists = await driver.exists("test/missing.txt")
        assert not exists

    @pytest.mark.asyncio
    async def test_delete_file(self, driver, mock_s3_client):
        """Test deleting file from S3"""
        await driver.delete("test/file.txt")

        mock_s3_client.delete_object.assert_called_once_with(
            Bucket="test-bucket", Key="test/file.txt",
        )

    @pytest.mark.asyncio
    async def test_get_presigned_url(self, driver, mock_s3_client):
        """Test generating presigned URL"""
        mock_s3_client.generate_presigned_url.return_value = "https://presigned-url"

        url = await driver.get_presigned_url("test/file.txt", expires_in=timedelta(hours=1))

        assert url == "https://presigned-url"
        mock_s3_client.generate_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_normalize_path(self, driver):
        """Test path normalization"""
        # Test with leading slash
        assert driver._normalize_path("/path/file.txt") == "path/file.txt"

        # Test with backslashes
        assert driver._normalize_path("path\\file.txt") == "path/file.txt"

        # Test normal path
        assert driver._normalize_path("path/file.txt") == "path/file.txt"
