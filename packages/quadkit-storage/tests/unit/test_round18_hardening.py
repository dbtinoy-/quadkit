"""Round-18 hardening pins for quadkit-storage.

Covers:
- azure/gcs exists(): connectivity/credentials failures must raise
  StorageError, never silently report "does not exist" (the old narrow
  except tuple also missed the SDK error classes entirely)
- kv/local boundaries: any error type is swallowed (never-raise contract)
- DI shutdown: one driver's close() failing must not skip closing the rest
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.storage.exceptions import StorageError


# ────────────────────────────────────────────────────────────
# Azure exists()
# ────────────────────────────────────────────────────────────


class TestAzureExistsErrorBoundary:
    @pytest.fixture
    def driver(self):
        """Constructed without __init__: the azure extra may be absent,
        and exists() only needs the container client + identifiers."""
        from quadkit.storage.backends.azure import AzureDriver

        d = AzureDriver.__new__(AzureDriver)
        d.account_name = "acct"
        d.container = "cont"
        d._container_client = MagicMock()
        return d

    @pytest.mark.asyncio
    async def test_sdk_error_raises_storage_error(self, driver) -> None:
        """A non-OSError SDK failure (credentials/network) must raise
        StorageError — the old narrow tuple let it escape raw, and a
        silent False would conflate outage with non-existence."""
        driver._container_client.get_blob_client.return_value.exists = AsyncMock(
            side_effect=RuntimeError("connection reset by peer")
        )
        with pytest.raises(StorageError):
            await driver.exists("file.txt")

    @pytest.mark.asyncio
    async def test_not_found_returns_false(self, driver) -> None:
        driver._container_client.get_blob_client.return_value.exists = AsyncMock(
            side_effect=Exception("ServiceRequestError: BlobNotFound (404)")
        )
        assert await driver.exists("file.txt") is False

    @pytest.mark.asyncio
    async def test_found_returns_true(self, driver) -> None:
        driver._container_client.get_blob_client.return_value.exists = AsyncMock(
            return_value=True
        )
        assert await driver.exists("file.txt") is True


# ────────────────────────────────────────────────────────────
# GCS exists()
# ────────────────────────────────────────────────────────────


class TestGcsExistsErrorBoundary:
    @pytest.fixture
    def driver(self):
        """Constructed without __init__: the gcs extra may be absent,
        and exists() only needs the client + identifiers."""
        from quadkit.storage.backends.gcs import GCSDriver

        d = GCSDriver.__new__(GCSDriver)
        d.bucket = "bkt"
        d.project_id = None
        d._client = MagicMock()
        return d

    @pytest.mark.asyncio
    async def test_api_core_error_raises_storage_error(self, driver) -> None:
        """google-api-core exceptions are not OSError/ConnectionError —
        the old tuple let them escape (or a silent False hid the outage)."""
        driver._client.download_metadata = AsyncMock(
            side_effect=PermissionError("403 Forbidden: insufficient scope")
        )
        with pytest.raises(StorageError):
            await driver.exists("file.txt")

    @pytest.mark.asyncio
    async def test_not_found_returns_false(self, driver) -> None:
        driver._client.download_metadata = AsyncMock(
            side_effect=Exception('404 Object not found: bkt/file.txt')
        )
        assert await driver.exists("file.txt") is False

    @pytest.mark.asyncio
    async def test_found_returns_true(self, driver) -> None:
        driver._client.download_metadata = AsyncMock(return_value={"name": "x"})
        assert await driver.exists("file.txt") is True


# ────────────────────────────────────────────────────────────
# KV local: never-raise boundary
# ────────────────────────────────────────────────────────────


class TestKvLocalNeverRaises:
    @pytest.fixture
    def store(self, tmp_path):
        from quadkit.storage.kv.local import LocalStorage

        return LocalStorage(base_path=str(tmp_path / "kv"))

    @pytest.mark.asyncio
    async def test_get_swallows_unexpected_error(self, store) -> None:
        """A surprise error type (not OSError/ValueError/RuntimeError)
        must return None, not propagate."""
        import quadkit.storage.kv.local as kv_local

        async def boom(path):
            raise MemoryError("disk full")

        original = kv_local.aiofiles.open
        kv_local.aiofiles.open = boom  # type: ignore[method-assign]
        try:
            assert await store.get("k", "ns") is None
        finally:
            kv_local.aiofiles.open = original  # type: ignore[method-assign]

    @pytest.mark.asyncio
    async def test_set_swallows_unexpected_error(self, store) -> None:
        import quadkit.storage.kv.local as kv_local

        async def boom(path):
            raise MemoryError("disk full")

        original = kv_local.aiofiles.open
        kv_local.aiofiles.open = boom  # type: ignore[method-assign]
        try:
            assert await store.set("k", "v", "ns") is False
        finally:
            kv_local.aiofiles.open = original  # type: ignore[method-assign]


# ────────────────────────────────────────────────────────────
# DI shutdown isolation
# ────────────────────────────────────────────────────────────


class TestShutdownIsolation:
    @pytest.mark.asyncio
    async def test_one_bad_close_does_not_skip_others(self) -> None:
        """A driver whose close() raises an unexpected error type must
        not prevent the remaining drivers from closing (the old
        (OSError, RuntimeError, ValueError) tuple let e.g. KeyError
        escape and abort the loop)."""
        from quadkit.storage.di.provider import StorageProvider

        provider = StorageProvider.__new__(StorageProvider)

        good = MagicMock()
        good.close = AsyncMock()
        bad = MagicMock()
        bad.close = AsyncMock(side_effect=KeyError("broken driver state"))

        provider._drivers = [("local", good), ("s3", bad)]

        # Must not raise — and the healthy driver still closes.
        await provider.shutdown()
        good.close.assert_awaited_once()


# ────────────────────────────────────────────────────────────
# _azure_helpers.reraise_blob_error
# ────────────────────────────────────────────────────────────


class TestReraiseBlobError:
    def _driver(self):
        d = MagicMock()
        d.container = "cont"
        d.account_name = "acct"
        return d

    def test_not_found_raises_file_not_found(self) -> None:
        from quadkit.storage.backends._azure_helpers import reraise_blob_error
        from quadkit.storage.exceptions import StorageFileNotFoundError

        with pytest.raises(StorageFileNotFoundError):
            reraise_blob_error(
                Exception("ServiceRequestError: BlobNotFound (404)"),
                self._driver(),
                "download",
                "f.txt",
            )

    def test_not_found_hint_varies_by_operation(self) -> None:
        from quadkit.storage.backends._azure_helpers import reraise_blob_error
        from quadkit.storage.exceptions import StorageFileNotFoundError

        for op in ("download", "stream", "delete", "info"):
            with pytest.raises(StorageFileNotFoundError) as exc_info:
                reraise_blob_error(
                    Exception("BlobNotFound 404"), self._driver(), op, "f.txt"
                )
            assert "cont" in str(exc_info.value.hint)

    def test_other_error_raises_storage_error(self) -> None:
        from quadkit.storage.backends._azure_helpers import reraise_blob_error
        from quadkit.storage.exceptions import StorageError

        with pytest.raises(StorageError):
            reraise_blob_error(
                RuntimeError("connection reset"), self._driver(), "delete", "f.txt"
            )

    def test_exception_chain_preserved(self) -> None:
        from quadkit.storage.backends._azure_helpers import reraise_blob_error
        from quadkit.storage.exceptions import StorageError

        cause = RuntimeError("connection reset")
        with pytest.raises(StorageError) as exc_info:
            reraise_blob_error(cause, self._driver(), "info", "f.txt")
        assert exc_info.value.__cause__ is cause
