"""Pure media asset size/mime policy shared by every multimedia package.

The URL-safety half of asset handling is NOT here — it is the SSRF
primitive ``quadkit.contracts.security.url_safety.is_safe_url_for_request``.
This module only encodes size and container policy that every consumer
(upscale, video, beat, the reference servers) enforces identically.
"""

from __future__ import annotations

DEFAULT_MAX_MEDIA_BYTES: int = 25 * 1024 * 1024

_ALLOWED_MEDIA_MIMES = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/gif",
        "video/mp4",
        "video/webm",
        "video/quicktime",
        "audio/mpeg",
        "audio/wav",
    }
)


def asset_bytes_ok(size: int, *, max_bytes: int = DEFAULT_MAX_MEDIA_BYTES) -> bool:
    """Return True if ``size`` bytes fit under ``max_bytes``."""

    return 0 <= size <= max_bytes


def assert_media_mime_allowed(mime_type: str) -> None:
    """Raise ValueError if ``mime_type`` is not in the framework media allowlist."""

    if mime_type not in _ALLOWED_MEDIA_MIMES:
        raise ValueError(f"mime_type not in media allowlist: {mime_type!r}")


__all__ = ["DEFAULT_MAX_MEDIA_BYTES", "assert_media_mime_allowed", "asset_bytes_ok"]
