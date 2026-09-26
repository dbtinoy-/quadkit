"""Tests for storage utilities."""

import pytest
import tempfile
from pathlib import Path

from quadkit.storage.lib.hashing import calculate_md5, calculate_sha256
from quadkit.storage.lib.content_type import get_content_type
from quadkit.storage.lib.paths import sanitize_path, is_safe_path, normalize_path


class TestCalculateMD5:
    """Tests for calculate_md5."""

    @pytest.mark.asyncio
    async def test_calculate_md5_bytes(self) -> None:
        """Should calculate MD5 of bytes."""
        data = b"hello world"
        result = await calculate_md5(data)
        assert result == "5eb63bbbe01eeed093cb22bb8f5acdc3"

    @pytest.mark.asyncio
    async def test_calculate_md5_empty_bytes(self) -> None:
        """Should calculate MD5 of empty bytes."""
        data = b""
        result = await calculate_md5(data)
        assert result == "d41d8cd98f00b204e9800998ecf8427e"


class TestCalculateSHA256:
    """Tests for calculate_sha256."""

    @pytest.mark.asyncio
    async def test_calculate_sha256_bytes(self) -> None:
        """Should calculate SHA256 of bytes."""
        data = b"hello world"
        result = await calculate_sha256(data)
        assert (
            result == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        )

    @pytest.mark.asyncio
    async def test_calculate_sha256_empty_bytes(self) -> None:
        """Should calculate SHA256 of empty bytes."""
        data = b""
        result = await calculate_sha256(data)
        assert (
            result == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )


class TestGetContentType:
    """Tests for get_content_type."""

    def test_jpeg_extension(self) -> None:
        """Should detect JPEG content type."""
        assert get_content_type("image.jpg") == "image/jpeg"

    def test_png_extension(self) -> None:
        """Should detect PNG content type."""
        assert get_content_type("image.png") == "image/png"

    def test_pdf_extension(self) -> None:
        """Should detect PDF content type."""
        assert get_content_type("document.pdf") == "application/pdf"

    def test_json_extension(self) -> None:
        """Should detect JSON content type."""
        assert get_content_type("data.json") == "application/json"

    def test_html_extension(self) -> None:
        """Should detect HTML content type."""
        assert get_content_type("page.html") == "text/html"

    def test_unknown_extension(self) -> None:
        """Should return a content type for unknown extension."""
        # The system may have different mappings, just verify we get a string
        result = get_content_type("file.xyz")
        assert isinstance(result, str)
        assert "/" in result

    def test_no_extension(self) -> None:
        """Should return application/octet-stream for no extension."""
        assert get_content_type("file") == "application/octet-stream"


class TestSanitizePath:
    """Tests for sanitize_path."""

    def test_basic_path(self) -> None:
        """Should pass through basic paths."""
        assert sanitize_path("file.txt") == "file.txt"
        assert sanitize_path("path/to/file.txt") == "path/to/file.txt"

    def test_removes_parent_traversal(self) -> None:
        """Should remove .. components."""
        assert sanitize_path("../etc/passwd") == "etc/passwd"
        assert sanitize_path("a/../b/file.txt") == "b/file.txt"

    def test_removes_current_directory(self) -> None:
        """Should remove . components."""
        assert sanitize_path("./file.txt") == "file.txt"
        assert sanitize_path("a/./b/file.txt") == "a/b/file.txt"

    def test_strips_slashes(self) -> None:
        """Should strip leading/trailing slashes."""
        assert sanitize_path("/file.txt") == "file.txt"
        assert sanitize_path("file.txt/") == "file.txt"

    def test_handles_empty(self) -> None:
        """Should handle empty paths."""
        assert sanitize_path("") == ""

    def test_windows_paths(self) -> None:
        """Should normalize Windows paths."""
        assert sanitize_path("a\\b\\file.txt") == "a/b/file.txt"


class TestIsSafePath:
    """Tests for is_safe_path."""

    def test_within_base(self):
        """Should return True for paths within base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = base / "subdir" / "file.txt"
            target.parent.mkdir()
            target.touch()
            
            assert is_safe_path(base, target) is True

    def test_outside_base(self):
        """Should return False for paths outside base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = Path("/etc/passwd")
            
            assert is_safe_path(base, target) is False

    def test_with_parent_traversal(self):
        """Should return False for paths with .. outside base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            target = base / ".." / ".." / "etc" / "passwd"
            
            assert is_safe_path(base, target) is False


class TestNormalizePath:
    """Tests for normalize_path."""

    def test_simple_path(self) -> None:
        """Should normalize simple paths."""
        assert normalize_path("file.txt") == "file.txt"
        assert normalize_path("path/to/file.txt") == "path/to/file.txt"

    def test_removes_parent_traversal(self) -> None:
        """Should resolve .. in paths."""
        assert normalize_path("a/../file.txt") == "file.txt"
        assert normalize_path("a/b/../file.txt") == "a/file.txt"

    def test_removes_current_directory(self) -> None:
        """Should resolve . in paths."""
        assert normalize_path("./file.txt") == "file.txt"

    def test_windows_to_posix(self) -> None:
        """Should convert Windows paths to POSIX style."""
        result = normalize_path("a\\b\\file.txt")
        assert "\\" not in result

    def test_strips_leading_slash(self) -> None:
        """Should strip leading slashes."""
        assert normalize_path("/file.txt") == "file.txt"

    def test_empty_path(self) -> None:
        """Should handle empty paths."""
        assert normalize_path("") == ""
