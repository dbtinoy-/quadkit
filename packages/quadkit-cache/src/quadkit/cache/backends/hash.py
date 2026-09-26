"""Cache key hashing utilities."""

from __future__ import annotations

import hashlib


def _compute_hash(data: str, algorithm: str = "blake2b") -> str:
    """Compute hash for cache key derivation.

    Args:
        data: Input data to hash.
        algorithm: Hash algorithm (blake2b, sha256). Defaults to blake2b.

    Returns:
        Hex-encoded hash digest.
    """
    if algorithm == "sha256":
        return hashlib.sha256(data.encode()).hexdigest()
    return hashlib.blake2b(data.encode(), digest_size=16).hexdigest()
