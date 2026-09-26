"""Path sanitization utilities"""

from __future__ import annotations

from pathlib import Path


def sanitize_path(path: str) -> str:
    """Sanitize a path to prevent directory traversal attacks"""
    # Normalize path separators
    path = path.replace("\\", "/")

    # Remove leading/trailing slashes
    path = path.strip("/")

    # Split into components
    parts = path.split("/")

    # Remove any '..' or '.' components
    sanitized_parts: list[str] = []
    for part in parts:
        if part == "..":
            # Remove parent directory if possible
            if sanitized_parts:
                sanitized_parts.pop()
        elif part in {".", ""}:
            # Skip current directory and empty parts
            continue
        else:
            sanitized_parts.append(part)

    return "/".join(sanitized_parts)


def is_safe_path(base_path: Path, target_path: Path) -> bool:
    """Check if target_path is within base_path (prevents directory traversal)"""
    try:
        target_path.resolve().relative_to(base_path.resolve())
        return True
    except ValueError:
        return False


def normalize_path(path: str) -> str:
    """Normalize a path using os.path.normpath and ensure POSIX style.

    Always returns a POSIX-style path (forward slashes) for consistency
    across platforms, as is standard for cloud-native frameworks.
    """
    if not path:
        return ""

    import os

    # os.path.normpath resolves .. and .
    normalized = os.path.normpath(path)

    # Convert to POSIX style (forward slashes)
    result = normalized.replace("\\", "/")

    # Strip a leading './' if it still exists (normpath usually removes it)
    if result.startswith("./"):
        result = result[2:]

    # Strip any leading slashes to remain relative to driver base
    return result.lstrip("/")
