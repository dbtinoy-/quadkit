"""Tests for storage protocol definitions."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.infra.storage.protocols import (
    BlobStoreProtocol,
)


class TestBlobStoreProtocol:
    """Tests for BlobStoreProtocol."""

    @pytest.mark.asyncio
    async def test_has_upload_method(self) -> None:
        """Test protocol has upload async method."""

        class Store:
            async def upload(
                self,
                path: str,
                data: bytes | Any,
                content_type: str | None = None,
                **options: Any,
            ) -> Any:
                return {"path": path, "size": 10}

        store = Store()
        result = await store.upload("path/to/file", b"data")
        assert result["path"] == "path/to/file"

    @pytest.mark.asyncio
    async def test_has_download_method(self) -> None:
        """Test protocol has download async method."""

        class Store:
            async def download(self, path: str) -> bytes:
                return b"content"

        store = Store()
        result = await store.download("path/to/file")
        assert result == b"content"

    def test_has_stream_method(self) -> None:
        """Test protocol has stream method."""

        class Store:
            def stream(self, path: str, chunk_size: int = 8192) -> Any:
                return iter([b"chunk1", b"chunk2"])

        store = Store()
        result = store.stream("path/to/file")
        chunks = list(result)
        assert len(chunks) == 2

    @pytest.mark.asyncio
    async def test_has_delete_method(self) -> None:
        """Test protocol has delete async method."""

        class Store:
            async def delete(self, path: str) -> None:
                pass

        store = Store()
        await store.delete("path/to/file")

    @pytest.mark.asyncio
    async def test_has_exists_method(self) -> None:
        """Test protocol has exists async method."""

        class Store:
            async def exists(self, path: str) -> bool:
                return True

        store = Store()
        result = await store.exists("path/to/file")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_info_method(self) -> None:
        """Test protocol has info async method."""

        class Store:
            async def info(self, path: str) -> Any:
                return {"path": path, "size": 100}

        store = Store()
        result = await store.info("path/to/file")
        assert result["size"] == 100

    def test_has_list_method(self) -> None:
        """Test protocol has list method."""

        class Store:
            def list(self, prefix: str = "") -> Any:
                return iter([{"path": "file1"}, {"path": "file2"}])

        store = Store()
        result = store.list("prefix/")
        files = list(result)
        assert len(files) == 2

    @pytest.mark.asyncio
    async def test_has_get_url_method(self) -> None:
        """Test protocol has get_url async method."""

        class Store:
            async def get_url(self, path: str) -> str:
                return "https://example.com/file"

        store = Store()
        result = await store.get_url("path/to/file")
        assert result.startswith("https")

    @pytest.mark.asyncio
    async def test_has_get_presigned_url_method(self) -> None:
        """Test protocol has get_presigned_url async method."""

        class Store:
            async def get_presigned_url(
                self,
                path: str,
                expires_in: Any = None,
                method: str = "GET",
            ) -> str:
                return "https://example.com/presigned"

        store = Store()
        result = await store.get_presigned_url("path/to/file")
        assert result.startswith("https")

    @pytest.mark.asyncio
    async def test_has_health_check_method(self) -> None:
        """Test protocol has health_check async method."""

        class Store:
            async def health_check(self, timeout: float = 5.0) -> Any:
                return {"status": "healthy"}

        store = Store()
        result = await store.health_check()
        assert result["status"] == "healthy"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Store:
            async def upload(self, path: str, data: Any, **kwargs: Any) -> Any:
                return {}

            async def download(self, path: str) -> bytes:
                return b""

            def stream(self, path: str, chunk_size: int = 8192) -> Any:
                return iter([])

            async def delete(self, path: str) -> None:
                pass

            async def exists(self, path: str) -> bool:
                return False

            async def info(self, path: str) -> Any:
                return {}

            def list(self, prefix: str = "") -> Any:
                return iter([])

            async def get_url(self, path: str) -> str:
                return ""

            async def get_presigned_url(
                self,
                path: str,
                expires_in: Any = None,
                method: str = "GET",
            ) -> str:
                return ""

            async def health_check(self, timeout: float = 5.0) -> Any:
                return {}

        assert isinstance(Store(), BlobStoreProtocol)
