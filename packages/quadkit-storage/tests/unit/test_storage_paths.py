"""Tests for storage path utilities."""

import pytest

from quadkit.storage.lib.paths import (
    is_safe_path,
    normalize_path,
    sanitize_path,
)


class TestSanitizePath:
    """Tests for sanitize_path."""

    def test_simple_path(self) -> None:
        """Should return simple path unchanged."""
        assert sanitize_path("folder/file.txt") == "folder/file.txt"

    def test_strips_leading_slash(self) -> None:
        """Should strip leading slashes."""
        assert sanitize_path("/folder/file.txt") == "folder/file.txt"

    def test_strips_trailing_slash(self) -> None:
        """Should strip trailing slashes."""
        assert sanitize_path("folder/file.txt/") == "folder/file.txt"

    def test_removes_double_dots(self) -> None:
        """Should remove parent directory references."""
        assert sanitize_path("folder/../file.txt") == "file.txt"

    def test_removes_single_dots(self) -> None:
        """Should remove current directory references."""
        assert sanitize_path("folder/./file.txt") == "folder/file.txt"

    def test_handles_windows_paths(self) -> None:
        """Should convert Windows backslashes."""
        assert sanitize_path("folder\\file.txt") == "folder/file.txt"

    def test_prevents_directory_traversal(self) -> None:
        """Should prevent directory traversal attacks."""
        result = sanitize_path("../../../etc/passwd")
        assert "etc" not in result or result == "etc/passwd"


class TestNormalizePath:
    """Tests for normalize_path."""

    def test_empty_path(self) -> None:
        """Should return empty string for empty input."""
        assert normalize_path("") == ""

    def test_simple_path(self) -> None:
        """Should return simple path."""
        assert normalize_path("folder/file.txt") == "folder/file.txt"

    def test_removes_current_dir(self) -> None:
        """Should remove ./ references."""
        assert normalize_path("./folder/file.txt") == "folder/file.txt"

    def test_normalizes_parent_dirs(self) -> None:
        """Should normalize parent directory references."""
        assert normalize_path("folder/../file.txt") == "file.txt"


class TestIsSafePath:
    """Tests for is_safe_path."""

    def test_same_path(self) -> None:
        """Should return True for same path."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path

            base = Path(tmpdir)
            target = base / "file.txt"
            target.touch()
            assert is_safe_path(base, target) is True

    def test_subdirectory(self) -> None:
        """Should return True for subdirectory."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path

            base = Path(tmpdir)
            target = base / "subdir" / "file.txt"
            target.parent.mkdir()
            target.touch()
            assert is_safe_path(base, target) is True

    def test_parent_directory(self) -> None:
        """Should return False for parent directory."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            from pathlib import Path

            base = Path(tmpdir)
            target = base / ".." / "other" / "file.txt"
            assert is_safe_path(base, target) is False
