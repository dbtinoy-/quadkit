"""Digest-based security hashers."""

from __future__ import annotations

import hashlib
import hmac


class Sha256Hasher:
    """Hash strings with SHA-256."""

    @property
    def algorithm(self) -> str:
        """Return the active hash algorithm name."""
        return "sha256"

    def digest(self, data: str | bytes) -> str:
        """Return the SHA-256 hex digest for *data*."""
        payload = data.encode("utf-8") if isinstance(data, str) else data
        return hashlib.sha256(payload).hexdigest()

    def verify_digest(self, data: str | bytes, expected: str) -> bool:
        """Compare *data* against an expected SHA-256 hex digest."""
        return hmac.compare_digest(self.digest(data), expected)

    async def hash(self, value: str) -> str:
        """Backward-compatible async alias for :meth:`digest`."""
        return self.digest(value)

    async def verify(self, value: str, hashed_value: str) -> bool:
        """Backward-compatible async alias for :meth:`verify_digest`."""
        return self.verify_digest(value, hashed_value)


class Blake2bHasher:
    """Hash strings with BLAKE2b."""

    def __init__(self, digest_size: int = 64) -> None:
        """Initialize the hasher.

        Args:
            digest_size: Digest size in bytes. Defaults to 64.
        """
        self._digest_size = digest_size

    @property
    def algorithm(self) -> str:
        """Return the active hash algorithm name."""
        return "blake2b"

    def digest(self, data: str | bytes) -> str:
        """Return the BLAKE2b hex digest for *data*."""
        payload = data.encode("utf-8") if isinstance(data, str) else data
        return hashlib.blake2b(
            payload,
            digest_size=self._digest_size,
        ).hexdigest()

    def verify_digest(self, data: str | bytes, expected: str) -> bool:
        """Compare *data* against an expected BLAKE2b hex digest."""
        return hmac.compare_digest(self.digest(data), expected)

    async def hash(self, value: str) -> str:
        """Backward-compatible async alias for :meth:`digest`."""
        return self.digest(value)

    async def verify(self, value: str, hashed_value: str) -> bool:
        """Backward-compatible async alias for :meth:`verify_digest`."""
        return self.verify_digest(value, hashed_value)
