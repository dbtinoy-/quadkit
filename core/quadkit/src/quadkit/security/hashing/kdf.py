"""Key derivation helpers for the security subsystem."""

from __future__ import annotations

import hashlib
import hmac
import os


class PBKDF2KDF:
    """PBKDF2-HMAC key derivation with a stable encoded format."""

    def __init__(
        self,
        *,
        algorithm: str = "pbkdf2_sha256",
        hash_name: str = "sha256",
        iterations: int = 100_000,
        salt_length: int = 16,
        dklen: int = 32,
    ) -> None:
        """Initialize the derivation helper.

        Args:
            algorithm: Stable prefix used in the encoded payload.
            hash_name: Underlying HMAC hash name for PBKDF2.
            iterations: PBKDF2 iteration count.
            salt_length: Salt length in bytes when one is generated.
            dklen: Derived key length in bytes.
        """
        self.algorithm = algorithm
        self.hash_name = hash_name
        self.iterations = iterations
        self.salt_length = salt_length
        self.dklen = dklen

    def _derive_bytes(self, secret: str, *, salt: bytes, dklen: int) -> bytes:
        """Derive raw bytes for *secret* using the configured algorithm."""
        return hashlib.pbkdf2_hmac(
            self.hash_name,
            secret.encode("utf-8"),
            salt,
            self.iterations,
            dklen=dklen,
        )

    async def derive(self, secret: str, *, salt: bytes | None = None) -> str:
        """Derive a stable encoded payload for *secret*."""
        salt_bytes = salt or os.urandom(self.salt_length)
        derived = self._derive_bytes(secret, salt=salt_bytes, dklen=self.dklen)
        return f"{self.algorithm}${self.iterations}${salt_bytes.hex()}${derived.hex()}"

    async def hash(self, secret: str, *, salt: bytes | None = None) -> str:
        """Alias for :meth:`derive` for API ergonomics."""
        return await self.derive(secret, salt=salt)

    async def verify(self, secret: str, encoded: str) -> bool:
        """Verify *secret* against an encoded PBKDF2 payload."""
        try:
            algorithm, iterations_text, salt_hex, key_hex = encoded.split("$", 3)
            if algorithm != self.algorithm:
                return False
            iterations = int(iterations_text)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(key_hex)
        except (AttributeError, ValueError):
            return False

        derived = hashlib.pbkdf2_hmac(
            self.hash_name,
            secret.encode("utf-8"),
            salt,
            iterations,
            dklen=len(expected),
        )
        return hmac.compare_digest(derived, expected)
