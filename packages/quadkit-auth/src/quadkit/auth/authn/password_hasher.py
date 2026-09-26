"""Argon2id-based password hashing implementations.

This module provides:
- Argon2idKeyDerivation: implements KeyDerivationProtocol (core security)
- Argon2idPasswordHasher: implements PasswordHasherProtocol (auth-domain)
- ComposedPasswordHasher: Argon2id-default hasher with a bcrypt legacy shim
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.auth import PasswordHasherProtocol
from quadkit.contracts.security.protocols import KeyDerivationProtocol
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.config import PasswordConfig

__all__ = [
    "Argon2idKeyDerivation",
    "Argon2idPasswordHasher",
    "ComposedPasswordHasher",
]

logger = get_logger(__name__)

_ARGON2_MEMORY_FLOOR = 19456


_argon2: Any
try:
    import argon2
    import argon2.exceptions

    _argon2 = argon2
    _argon2_available = True
except ImportError:
    _argon2 = None
    _argon2_available = False


class Argon2idKeyDerivation(KeyDerivationProtocol):
    """Argon2id key derivation implementation.

    Implements KeyDerivationProtocol using argon2-cffi.
    Follows OWASP 2024 recommendations for parameters.
    """

    def __init__(self, config: PasswordConfig | None = None) -> None:
        if not _argon2_available:
            raise RuntimeError("argon2-cffi is not installed")
        self._ph = _argon2.PasswordHasher(
            memory_cost=65536,  # 64 MiB
            time_cost=3,
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )

    async def derive(self, secret: str, *, salt: bytes | None = None) -> str:
        """Derive a key from a secret using Argon2id."""

        def _derive_sync() -> str:
            return cast("str", self._ph.hash(secret))

        return await asyncio.to_thread(_derive_sync)

    async def verify(self, secret: str, encoded: str) -> bool:
        """Verify a secret against an Argon2id hash."""

        def _verify_sync() -> bool:
            try:
                self._ph.verify(encoded, secret)
                return True
            except Exception:  # noqa: BLE001 — fail closed: any verification failure (incl. InvalidHashError on malformed input) is a mismatch
                return False

        return await asyncio.to_thread(_verify_sync)

    async def hash(self, secret: str, *, salt: bytes | None = None) -> str:
        """Backward-compatible alias for derive."""
        return await self.derive(secret, salt=salt)


class Argon2idPasswordHasher(PasswordHasherProtocol):
    """Auth-domain password hasher using Argon2id.

    Implements PasswordHasherProtocol (hash/verify) and delegates
    to KeyDerivationProtocol internally.
    """

    def __init__(self, kdf: KeyDerivationProtocol) -> None:
        self._kdf = kdf

    async def hash(self, password: str) -> str:
        """Hash a password using Argon2id."""
        return await self._kdf.derive(password)

    async def verify(self, password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return await self._kdf.verify(password, hashed_password)

    def needs_rehash(self, hashed_password: str) -> bool:
        """Compare the stored hash's memory cost against the OWASP floor.

        Parses the Argon2id encoded prefix (``$argon2id$v=19$m=...,t=...,p=...``);
        returns ``True`` when the stored memory cost is below the 19456 KiB
        floor.  Unparseable or unknown formats return ``True`` (fail-closed).

        Args:
            hashed_password: Stored Argon2id hash string.

        Returns:
            True when the hash should be re-computed at current parameters.
        """
        if not isinstance(hashed_password, str) or not hashed_password:
            return True
        try:
            parts = hashed_password.split("$")
            if parts[1] == "argon2id":
                match = re.search(r"m=(\d+)", parts[3])
                if match:
                    return int(match.group(1)) < _ARGON2_MEMORY_FLOOR
        except (ValueError, IndexError, TypeError):
            logger.warning(
                "password_hash_cost_unparseable",
                hash_prefix=hashed_password[:7],
            )
        return True

    async def rehash_if_needed(
        self,
        password: str,
        hashed_password: str | None,
    ) -> str | None:
        """Rehash the password when the stored hash is below the cost floor.

        Args:
            password: Plain text password (already verified).
            hashed_password: Stored hash string, or None.

        Returns:
            A fresh hash when an upgrade is needed, else None.
        """
        if not hashed_password:
            return None
        if self.needs_rehash(hashed_password):
            return await self.hash(password)
        return None


class ComposedPasswordHasher(PasswordHasherProtocol):
    """Argon2id-default composed hasher with a bcrypt legacy shim (ODD-1 A).

    New hashes use the primary (Argon2id) hasher.  Stored bcrypt hashes
    continue to verify through the legacy shim and are flagged by
    :meth:`needs_rehash` (algorithm differs from the default) so
    ``rehash_if_needed`` upgrades them on the user's next successful login.
    """

    def __init__(
        self,
        primary: PasswordHasherProtocol,
        legacy: PasswordHasherProtocol,
    ) -> None:
        self._primary = primary
        self._legacy = legacy

    async def hash(self, password: str) -> str:
        """Hash a password with the primary (Argon2id) hasher."""
        return await self._primary.hash(password)

    async def verify(self, password: str, hashed_password: str) -> bool:
        """Verify a password, dispatching on the stored hash's algorithm.

        Bcrypt-prefixed (``$2*$``) hashes route to the legacy shim; Argon2id
        hashes route to the primary hasher; anything else fails closed.
        """
        if not isinstance(hashed_password, str) or not hashed_password:
            return False
        if hashed_password.startswith("$2"):
            return await self._legacy.verify(password, hashed_password)
        return await self._primary.verify(password, hashed_password)

    def needs_rehash(self, hashed_password: str) -> bool:
        """Return True when the stored hash is not at current parameters.

        Argon2id hashes below the memory floor are flagged by the primary;
        any bcrypt hash differs from the Argon2id default and is upgraded on
        the next successful login.  Unknown formats return True (fail-closed).
        """
        if not isinstance(hashed_password, str) or not hashed_password:
            return True
        if hashed_password.startswith("$argon2id$"):
            return self._primary.needs_rehash(hashed_password)
        return True

    async def rehash_if_needed(
        self,
        password: str,
        hashed_password: str | None,
    ) -> str | None:
        """Rehash the password when the stored hash is below the cost target.

        Args:
            password: Plain text password (already verified).
            hashed_password: Stored hash string, or None.

        Returns:
            A fresh hash when an upgrade is needed, else None.
        """
        if not hashed_password:
            return None
        if self.needs_rehash(hashed_password):
            return await self.hash(password)
        return None
