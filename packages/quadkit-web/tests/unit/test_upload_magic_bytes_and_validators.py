"""Unit tests for quadkit.web.uploads magic-byte and metadata validators."""

from __future__ import annotations

import io
from types import SimpleNamespace

import pytest

from quadkit.web.exceptions import BadRequestError
from quadkit.web.uploads import (
    SAFE_MEDIA_RESPONSE_HEADERS,
    FileUpload,
    MagicByteValidator,
    extension_for_mime_type,
    sanitize_blob_key,
    sniff_mime_type,
    validate_upload_bytes,
    validate_upload_metadata,
)

ALLOWED = ("image/jpeg", "image/png", "image/webp", "application/pdf")


def test_sniff_mime_type_identifies_common_headers() -> None:
    """sniff_mime_type detects JPEG, PNG, GIF, WebP, and PDF headers."""
    assert sniff_mime_type(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "image/jpeg"
    assert sniff_mime_type(b"\x89PNG\r\n\x1a\n\x00\x00") == "image/png"
    assert sniff_mime_type(b"GIF89a\x01\x00") == "image/gif"
    assert sniff_mime_type(b"RIFF\x24\x00\x00\x00WEBP") == "image/webp"
    assert sniff_mime_type(b"%PDF-1.7\n") == "application/pdf"
    assert sniff_mime_type(b"plain text") is None


def test_validate_upload_metadata_and_bytes_enforce_mime_size_and_magic() -> None:
    """validate_upload_bytes rejects spoofed MIME headers and oversized payloads."""
    assert validate_upload_metadata(
        "image/png",
        1024,
        max_size_bytes=2048,
        allowed_types=ALLOWED,
    ).is_ok()
    assert validate_upload_metadata(
        "application/x-msdownload",
        10,
        max_size_bytes=2048,
        allowed_types=ALLOWED,
    ).is_err()

    valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    assert validate_upload_bytes(
        valid_png,
        "image/png",
        max_size_bytes=2048,
        allowed_types=ALLOWED,
    ).is_ok()

    # Spoofed HTML claiming to be PNG must fail magic-byte check
    spoofed = validate_upload_bytes(
        b"<html><script>alert(1)</script></html>",
        "image/png",
        max_size_bytes=2048,
        allowed_types=ALLOWED,
    )
    assert spoofed.is_err()
    assert "does not match" in spoofed.unwrap_err().message


@pytest.mark.asyncio
async def test_magic_byte_validator_rewinds_upload_stream() -> None:
    """MagicByteValidator inspects header bytes and rewinds the stream for downstream readers."""
    buf = io.BytesIO(b"\xff\xd8\xff\xe0hello")

    class _FakeUploadFile:
        async def read(self, size: int = -1) -> bytes:
            return buf.read(size)

        async def seek(self, offset: int) -> None:
            buf.seek(offset)

    upload = FileUpload(
        filename="pet.jpg",
        content_type="image/jpeg",
        size=9,
        file=_FakeUploadFile(),  # type: ignore[arg-type]
    )
    res = await MagicByteValidator(allowed_types=ALLOWED).validate(upload)
    assert res.is_ok()
    assert await upload.read() == b"\xff\xd8\xff\xe0hello"
    _ = SimpleNamespace()


def test_sanitize_blob_key_and_extension_for_mime_type() -> None:
    """sanitize_blob_key blocks traversal and extension_for_mime_type ignores spoofed suffixes."""
    assert sanitize_blob_key("uploads/pets/avatar.png") == "uploads/pets/avatar.png"
    for bad in (
        "",
        "/etc/passwd",
        "../secret",
        "uploads/../../secret",
        "a\\b",
        "a\x00b",
    ):
        with pytest.raises(BadRequestError):
            sanitize_blob_key(bad)

    assert extension_for_mime_type("image/jpeg") == ".jpg"
    assert extension_for_mime_type("image/png; charset=binary") == ".png"
    assert extension_for_mime_type("image/webp") == ".webp"
    assert extension_for_mime_type(None) == ""
    assert SAFE_MEDIA_RESPONSE_HEADERS["X-Content-Type-Options"] == "nosniff"
