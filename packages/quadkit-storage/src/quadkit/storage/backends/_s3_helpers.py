"""Object-metadata/body helpers for the AWS S3 driver.

Pure utilities extracted from :mod:`quadkit.storage.backends.s3`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast


def parse_last_modified(value: Any) -> datetime:
    """Normalise an S3 ``LastModified`` value into a UTC datetime.

    Accepts ISO-8601 strings (as returned by some S3-compatible endpoints)
    or datetimes; falls back to the current UTC time.
    """
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    if isinstance(value, datetime):
        return value
    return datetime.now(UTC)


def coerce_body_bytes(res: Any) -> bytes:
    """Normalise a body-read result to bytes across client implementations."""
    if isinstance(res, (bytes, bytearray)):
        return bytes(res)
    if isinstance(res, str):
        return res.encode("utf-8")
    return cast("bytes", res)
