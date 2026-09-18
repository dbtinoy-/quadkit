"""Tests for multimedia asset-size/mime policy (security spec D1)."""

from __future__ import annotations

import pytest

from quadkit.contracts.multimedia.security import (
    DEFAULT_MAX_MEDIA_BYTES,
    asset_bytes_ok,
    assert_media_mime_allowed,
)


class TestMediaSecurityPolicy:
    def test_default_cap_is_25_mib(self) -> None:
        assert DEFAULT_MAX_MEDIA_BYTES == 25 * 1024 * 1024

    @pytest.mark.parametrize(
        ("size", "expected"),
        [
            (0, True),
            (DEFAULT_MAX_MEDIA_BYTES, True),
            (DEFAULT_MAX_MEDIA_BYTES + 1, False),
        ],
    )
    def test_asset_bytes_ok(self, size: int, expected: bool) -> None:
        assert asset_bytes_ok(size) is expected

    def test_asset_bytes_ok_respects_custom_cap(self) -> None:
        assert asset_bytes_ok(10, max_bytes=5) is False

    @pytest.mark.parametrize(
        "mime",
        [
            "image/png",
            "image/jpeg",
            "image/gif",
            "video/mp4",
            "video/webm",
            "audio/wav",
            "audio/mpeg",
            "video/quicktime",
        ],
    )
    def test_known_mimes_allowed(self, mime: str) -> None:
        assert_media_mime_allowed(mime)  # must not raise

    @pytest.mark.parametrize("mime", ["application/pdf", "text/html", ""])
    def test_unknown_mimes_rejected(self, mime: str) -> None:
        with pytest.raises(ValueError):
            assert_media_mime_allowed(mime)
