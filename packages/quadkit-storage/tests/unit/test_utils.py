"""Unit tests for storage utilities"""

from pathlib import Path
from unittest.mock import patch

import pytest

from quadkit.storage.lib.content_type import (
    get_content_type,
    get_content_type_from_data,
)
from quadkit.storage.lib.hashing import (
    calculate_md5,
    calculate_sha256,
)
from quadkit.storage.lib.paths import is_safe_path, normalize_path, sanitize_path


class TestContentType:
    """Test content type utilities"""

    def test_get_content_type_known_extension(self):
        """Test content type detection for known file extensions"""
        assert get_content_type("test.txt") == "text/plain"
        assert get_content_type("test.jpg") == "image/jpeg"
        assert get_content_type("test.pdf") == "application/pdf"

    def test_get_content_type_unknown_extension(self):
        """Test content type fallback for unknown extensions"""
        assert get_content_type("test.unknown") == "application/octet-stream"

    def test_get_content_type_no_extension(self):
        """Test content type for files without extensions"""
        assert get_content_type("README") == "application/octet-stream"

    def test_get_content_type_from_data_with_magic(self, monkeypatch):
        """Test content type detection from data using python-magic"""
        import sys

        class _FakeMagic:
            @staticmethod
            def from_buffer(buf, mime=True):
                return "image/png"

        # Inject a fake 'magic' module into sys.modules so tests don't require libmagic
        monkeypatch.setitem(sys.modules, "magic", _FakeMagic)

        result = get_content_type_from_data(b"fake png data")
        assert result == "image/png"

    def test_get_content_type_from_data_without_magic(self):
        """Test content type detection fallback when python-magic is not available"""
        with patch.dict("sys.modules", {"magic": None}):
            result = get_content_type_from_data(b"some data")
            assert result == "application/octet-stream"


class TestHashing:
    """Test hashing utilities"""

    @pytest.mark.asyncio
    async def test_calculate_md5(self):
        """Test MD5 calculation for async iterator"""

        async def data_generator():
            yield b"chunk1"
            yield b"chunk2"
            yield b"chunk3"

        result = await calculate_md5(data_generator())
        expected = "2aca0a9378723b1bed59975523ed50cd"  # MD5 of "chunk1chunk2chunk3"
        assert result == expected

    @pytest.mark.asyncio
    async def test_calculate_sha256(self):
        """Test SHA256 calculation for async iterator"""

        async def data_generator():
            yield b"chunk1"
            yield b"chunk2"
            yield b"chunk3"

        result = await calculate_sha256(data_generator())
        expected = "bfe08b41e4577d49fb775d1dbc69d2db429bcec209e4637370cd88f2d6c96469"  # SHA256 of "chunk1chunk2chunk3"
        assert result == expected

    @pytest.mark.asyncio
    async def test_calculate_md5_bytes(self):
        """Test MD5 calculation for bytes"""
        data = b"Hello World"
        result = await calculate_md5(data)
        expected = "b10a8db164e0754105b7a99be72e3fe5"  # MD5 of "Hello World"
        assert result == expected

    @pytest.mark.asyncio
    async def test_calculate_sha256_bytes(self):
        """Test SHA256 calculation for bytes"""
        data = b"Hello World"
        result = await calculate_sha256(data)
        expected = "a591a6d40bf420404a011733cfb7b190d62c65bf0bcda32b57b277d9ad9f146e"  # SHA256 of "Hello World"
        assert result == expected


class TestPaths:
    """Test path utilities"""

    def test_sanitize_path_basic(self):
        """Test basic path sanitization"""
        assert sanitize_path("path/to/file.txt") == "path/to/file.txt"
        assert sanitize_path("/absolute/path/file.txt") == "absolute/path/file.txt"
        assert sanitize_path("path/file.txt/") == "path/file.txt"

    def test_sanitize_path_directory_traversal(self):
        """Test path sanitization prevents directory traversal"""
        assert sanitize_path("../etc/passwd") == "etc/passwd"
        assert sanitize_path("../../../etc/passwd") == "etc/passwd"
        assert sanitize_path("path/../../../file.txt") == "file.txt"

    def test_sanitize_path_current_directory(self):
        """Test path sanitization handles current directory references"""
        assert sanitize_path("./file.txt") == "file.txt"
        assert sanitize_path("path/./file.txt") == "path/file.txt"
        assert sanitize_path("path/.") == "path"

    def test_sanitize_path_empty_parts(self):
        """Test path sanitization handles empty parts"""
        assert sanitize_path("path//file.txt") == "path/file.txt"
        assert sanitize_path("//path/file.txt") == "path/file.txt"

    def test_sanitize_path_complex_traversal(self):
        """Test complex directory traversal scenarios"""
        assert sanitize_path("a/b/../c") == "a/c"
        assert sanitize_path("a/../b/c/../d") == "b/d"
        assert sanitize_path("../a/b/../c") == "a/c"

    def test_is_safe_path_safe(self):
        """Test safe path validation"""
        base = Path("/home/user")
        safe_path = Path("/home/user/documents/file.txt")
        assert is_safe_path(base, safe_path) is True

    def test_is_safe_path_unsafe(self):
        """Test unsafe path detection"""
        base = Path("/home/user")
        unsafe_path = Path("/etc/passwd")
        assert is_safe_path(base, unsafe_path) is False

    def test_is_safe_path_traversal(self):
        """Test directory traversal detection"""
        base = Path("/home/user")
        traversal_path = Path("/home/user/../../../etc/passwd")
        assert is_safe_path(base, traversal_path) is False

    def test_is_safe_path_relative(self):
        """Test relative path safety"""
        base = Path("/tmp")
        relative_path = Path("/tmp/../etc/passwd")
        assert is_safe_path(base, relative_path) is False

    def test_normalize_path(self):
        """Test path normalization"""
        assert normalize_path("path/to/../file.txt") == "path/file.txt"
        assert normalize_path("./path/to/file.txt") == "path/to/file.txt"
        assert normalize_path("path//to/file.txt") == "path/to/file.txt"

    @pytest.mark.skipif("os.name != 'nt'", reason="Windows-specific path normalization")
    def test_normalize_path_windows(self):
        """Test Windows path normalization"""
        assert normalize_path("path\\to\\file.txt") == "path\\to\\file.txt"
