"""Tests for storage models."""

import pytest
from datetime import datetime, UTC

from quadkit.contracts.infra.storage.models import FileInfo


class TestFileInfo:
    """Tests for FileInfo."""

    def test_file_info_creation(self) -> None:
        """Test creating a FileInfo."""
        now = datetime.now(UTC)
        info = FileInfo(
            path="/uploads/test.txt",
            size=1024,
            content_type="text/plain",
            last_modified=now,
        )
        assert info.path == "/uploads/test.txt"
        assert info.size == 1024
        assert info.content_type == "text/plain"
        assert info.last_modified == now

    def test_file_info_with_etag(self) -> None:
        """Test FileInfo with etag."""
        now = datetime.now(UTC)
        info = FileInfo(
            path="/uploads/test.txt",
            size=1024,
            content_type="text/plain",
            last_modified=now,
            etag="abc123",
        )
        assert info.etag == "abc123"

    def test_file_info_with_metadata(self) -> None:
        """Test FileInfo with metadata."""
        now = datetime.now(UTC)
        info = FileInfo(
            path="/uploads/test.txt",
            size=1024,
            content_type="text/plain",
            last_modified=now,
            metadata={"author": "test"},
        )
        assert info.metadata == {"author": "test"}
