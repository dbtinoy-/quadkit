"""Filename and SQL LIKE sanitizers."""

from __future__ import annotations

import re


class FilenameSanitizer:
    """Sanitizer for filenames and SQL LIKE values."""

    _FILENAME_UNSAFE_RE = re.compile(r"[^a-zA-Z0-9.\-_]")

    def sanitize_filename(self, filename: str) -> str:
        """Keep only safe characters in filenames."""
        if not filename:
            return filename

        sanitized = filename.replace("/", "").replace("\\", "")
        sanitized = self._FILENAME_UNSAFE_RE.sub("_", sanitized)

        if not sanitized or sanitized.startswith("."):
            return "unnamed_file"

        return sanitized

    def sanitize_sql_like(self, value: str, escape_char: str = "\\") -> str:
        """Escape SQL LIKE wildcards in the provided value."""
        if not value:
            return value

        return (
            value.replace(escape_char, escape_char * 2)
            .replace("%", f"{escape_char}%")
            .replace("_", f"{escape_char}_")
        )


__all__ = ["FilenameSanitizer"]
