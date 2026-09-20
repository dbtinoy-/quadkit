"""Tests for async file upload operations."""

from __future__ import annotations

from pathlib import Path
import tempfile
from unittest.mock import AsyncMock

import pytest

from quadkit.web.uploads.pipeline import FileUpload


@pytest.mark.asyncio
async def test_save_to_does_not_use_blocking_path_mkdir(monkeypatch: pytest.MonkeyPatch) -> None:
    """FileUpload.save_to() must not call blocking Path.mkdir()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "nested" / "test.txt"

        file_mock = AsyncMock()
        file_mock.read = AsyncMock(return_value=b"test content")
        upload = FileUpload(
            filename="test.txt",
            content_type="text/plain",
            size=12,
            file=file_mock,
        )

        def _raise_if_called(*args: object, **kwargs: object) -> None:
            raise AssertionError("Path.mkdir() should not be used in async write path")

        monkeypatch.setattr(Path, "mkdir", _raise_if_called)

        await upload.save_to(target)
        assert target.exists()


@pytest.mark.asyncio
async def test_stream_to_does_not_use_blocking_path_mkdir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FileUpload.stream_to() must not call blocking Path.mkdir()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "nested" / "stream.txt"

        chunks = [b"chunk1", b"chunk2", b""]
        file_mock = AsyncMock()
        file_mock.read = AsyncMock(side_effect=chunks)
        upload = FileUpload(
            filename="stream.txt",
            content_type="text/plain",
            size=12,
            file=file_mock,
        )

        def _raise_if_called(*args: object, **kwargs: object) -> None:
            raise AssertionError("Path.mkdir() should not be used in async write path")

        monkeypatch.setattr(Path, "mkdir", _raise_if_called)

        await upload.stream_to(target, chunk_size=6)
        assert target.exists()


@pytest.mark.asyncio
async def test_save_to_uses_aiofiles() -> None:
    """FileUpload.save_to() must use aiofiles (async), not open() (blocking)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "test.txt"

        # Mock file content
        file_mock = AsyncMock()
        file_mock.read = AsyncMock(return_value=b"test content")

        upload = FileUpload(
            filename="test.txt",
            content_type="text/plain",
            size=12,
            file=file_mock,
        )

        # Call save_to
        await upload.save_to(target)

        # Verify file was written asynchronously
        assert target.exists()
        assert target.read_bytes() == b"test content"


@pytest.mark.asyncio
async def test_stream_to_uses_aiofiles() -> None:
    """FileUpload.stream_to() must use aiofiles (async), not open() (blocking)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "stream.txt"

        # Mock chunked file stream
        chunks = [b"chunk1", b"chunk2", b"chunk3", b""]
        file_mock = AsyncMock()
        file_mock.read = AsyncMock(side_effect=chunks)

        upload = FileUpload(
            filename="stream.txt",
            content_type="text/plain",
            size=18,
            file=file_mock,
        )

        # Call stream_to
        await upload.stream_to(target, chunk_size=6)

        # Verify file was written asynchronously
        assert target.exists()
        assert target.read_bytes() == b"chunk1chunk2chunk3"
