from __future__ import annotations

from collections.abc import AsyncIterator
import hashlib


async def calculate_md5(data: bytes | AsyncIterator[bytes]) -> str:
    """Calculate MD5 hash of bytes or streaming data.

    Args:
        data: In-memory bytes or an async iterator of bytes.

    Returns:
        Hexadecimal MD5 hash.
    """
    if isinstance(data, bytes):
        return hashlib.md5(data, usedforsecurity=False).hexdigest()

    hash_md5 = hashlib.md5(usedforsecurity=False)
    async for chunk in data:
        hash_md5.update(chunk)
    return hash_md5.hexdigest()


async def calculate_sha256(data: bytes | AsyncIterator[bytes]) -> str:
    """Calculate SHA256 hash of bytes or streaming data.

    Args:
        data: In-memory bytes or an async iterator of bytes.

    Returns:
        Hexadecimal SHA256 hash.
    """
    if isinstance(data, bytes):
        return hashlib.sha256(data).hexdigest()

    hash_sha256 = hashlib.sha256()
    async for chunk in data:
        hash_sha256.update(chunk)
    return hash_sha256.hexdigest()
