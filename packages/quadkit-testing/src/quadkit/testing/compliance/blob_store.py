"""Contract compliance suite for ``BlobStoreProtocol`` implementations.

Subclass :class:`BlobStoreCompliance` and implement
:meth:`create_store` to verify any blob store satisfies the
``BlobStoreProtocol`` contract::

    from quadkit.testing.compliance import BlobStoreCompliance

    class TestLocalDriverCompliance(BlobStoreCompliance):
        async def create_store(self):
            return LocalDriver(root="/tmp/compliance-test")
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pytest

__all__ = ["BlobStoreCompliance"]


class BlobStoreCompliance:
    """Reusable test suite for any ``BlobStoreProtocol`` implementation.

    Subclass and implement :meth:`create_store`:

    .. code-block:: python

        class TestMyBlobStore(BlobStoreCompliance):
            async def create_store(self):
                return LocalDriver(root="/tmp/test")
    """

    @abstractmethod
    async def create_store(self) -> Any:
        """Return a ready-to-use, empty BlobStoreProtocol under test."""
        ...

    # ------------------------------------------------------------------
    # Upload / download round-trip
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_upload_and_download(self) -> None:
        """upload then download returns the same bytes."""
        store = await self.create_store()
        content = b"compliance-test-payload"
        await store.upload("test/file.bin", content)
        result = await store.download("test/file.bin")
        assert result == content

    # ------------------------------------------------------------------
    # Existence checks
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_exists_after_upload(self) -> None:
        """exists returns True after a file is uploaded."""
        store = await self.create_store()
        await store.upload("test/exists.bin", b"data")
        assert await store.exists("test/exists.bin") is True

    @pytest.mark.asyncio
    async def test_not_exists_for_missing_path(self) -> None:
        """exists returns False for a path that has never been uploaded."""
        store = await self.create_store()
        assert await store.exists("test/does-not-exist.bin") is False

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_removes_file(self) -> None:
        """delete removes the file; exists returns False afterwards."""
        store = await self.create_store()
        await store.upload("test/to-delete.bin", b"gone")
        await store.delete("test/to-delete.bin")
        assert await store.exists("test/to-delete.bin") is False

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_returns_uploaded_paths(self) -> None:
        """list with a prefix returns paths of uploaded objects."""
        store = await self.create_store()
        await store.upload("prefix/a.bin", b"a")
        await store.upload("prefix/b.bin", b"b")
        paths = [item async for item in store.list("prefix/")]
        path_strs = [str(p) for p in paths]
        assert any("a.bin" in p for p in path_strs)
        assert any("b.bin" in p for p in path_strs)

    # ------------------------------------------------------------------
    # URL generation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_url_returns_string(self) -> None:
        """get_url returns a non-empty string."""
        store = await self.create_store()
        await store.upload("test/url.bin", b"data")
        url = await store.get_url("test/url.bin")
        assert isinstance(url, str)
        assert url

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_health_check_returns_result(self) -> None:
        """health_check returns a HealthCheckResult."""
        store = await self.create_store()
        result = await store.health_check(timeout=5.0)
        assert result is not None
        assert hasattr(result, "status")
