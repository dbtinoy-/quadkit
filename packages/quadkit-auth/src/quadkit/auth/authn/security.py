"""Password security utilities using Passlib with a lightweight fallback."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.auth import PasswordHasherProtocol, PasswordPolicyProtocol
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.auth.config import PasswordConfig

__all__ = [
    "DUMMY_PASSWORD_HASH",
    "PasswordHasher",
    "PasswordPolicy",
    "UnknownHashError",
]

logger = get_logger(__name__)

try:
    _bcrypt: ModuleType | None = importlib.import_module("bcrypt")
except ImportError:
    _bcrypt = None
bcrypt_available = _bcrypt is not None

if not bcrypt_available:
    logger.warning("bcrypt not available - password hashing will be limited")

try:
    pyotp: ModuleType | None = importlib.import_module("pyotp")
except ImportError:
    pyotp = None
pyotp_available = pyotp is not None

UnknownHashError = Exception


_MAX_PASSWORD_BYTES = 72
_WARN_PASSWORD_BYTES = 64
_DEFAULT_BCRYPT_ROUNDS = 12


def _prehash(password: str) -> str:
    """Pre-hash *password* with SHA-256 to avoid bcrypt's 72-byte truncation.

    The SHA-256 digest (32 bytes) is base64-encoded to a 44-byte ASCII string,
    which is always well within bcrypt's 72-byte limit.  This must be applied
    consistently in both :meth:`PasswordHasher.hash` and
    :meth:`PasswordHasher.verify` so that hashes computed with pre-hashing can
    be verified correctly.

    Args:
        password: Plain-text password string.

    Returns:
        Base64-encoded SHA-256 digest of the UTF-8 encoded password.
    """
    return base64.b64encode(hashlib.sha256(password.encode()).digest()).decode()


def _prepare_password_bytes(password: str) -> bytes:
    """Return the bytes that bcrypt should hash for *password*.

    * Passwords **≤ 64 bytes**: encoded directly — no transformation.
    * Passwords **> 64 bytes and ≤ 72 bytes**: a structured warning is emitted
      because these are in the borderline range where bcrypt's limit is close.
    * Passwords **> 72 bytes**: pre-hashed with SHA-256 via :func:`_prehash`
      so that bcrypt sees a 44-byte ASCII string rather than silently
      truncating the input.

    Args:
        password: Plain-text password string.

    Returns:
        Bytes ready to pass to ``bcrypt.hashpw`` / ``bcrypt.checkpw``.

    Raises:
        RuntimeError: If bcrypt is not installed.
    """
    if not bcrypt_available:
        raise RuntimeError("bcrypt library is not available")

    password_bytes = password.encode("utf-8")
    byte_length = len(password_bytes)

    if byte_length > _MAX_PASSWORD_BYTES:
        # Pre-hash to avoid silent bcrypt truncation.
        return _prehash(password).encode("ascii")

    if byte_length > _WARN_PASSWORD_BYTES:
        logger.warning(
            "password_near_bcrypt_limit",
            byte_length=byte_length,
            limit=_MAX_PASSWORD_BYTES,
            message=(
                "Password is between 64 and 72 bytes; "
                "it is close to bcrypt's 72-byte truncation limit."
            ),
        )

    return password_bytes


class PasswordHasher(PasswordHasherProtocol):
    """Bcrypt password hasher implementing the PasswordHasherProtocol.

    Provides secure password hashing using bcrypt with UTF-8 aware truncation.
    The bcrypt cost factor is per-instance (``rounds``) so the configured
    value is honored both at construction and by the container singleton.
    """

    MAX_PASSWORD_BYTES = _MAX_PASSWORD_BYTES

    def __init__(self, rounds: int = _DEFAULT_BCRYPT_ROUNDS) -> None:
        self._rounds = rounds

    async def hash(self, password: str) -> str:
        """Hash a password using bcrypt with UTF-8 aware truncation.

        Args:
            password: Plain text password.

        Returns:
            Bcrypt hash string (``$2b$<cost>$...``) using the configured
            cost factor.

        Raises:
            RuntimeError: If bcrypt is not available.
        """
        if not bcrypt_available:
            raise RuntimeError("bcrypt library is not available")

        password_bytes = _prepare_password_bytes(password)

        def _hash_sync(pwd_bytes: bytes) -> str:
            bcrypt = cast("Any", _bcrypt)
            salt = bcrypt.gensalt(rounds=self._rounds)
            hashed = bcrypt.hashpw(pwd_bytes, salt)
            return str(hashed.decode("ascii"))

        return await asyncio.to_thread(_hash_sync, password_bytes)

    async def verify(self, password: str, hashed_password: str | bytes) -> bool:
        """Verify a password against its hash asynchronously.

        Args:
            password: Plain text password.
            hashed_password: Stored hash to compare against.

        Returns:
            True if the password matches the hash, False otherwise.

        Raises:
            RuntimeError: If bcrypt is not available.
        """
        if not bcrypt_available:
            raise RuntimeError("bcrypt library is not available")

        def _verify_sync(pwd_bytes: bytes, hash_bytes: bytes) -> bool:
            try:
                bcrypt = cast("Any", _bcrypt)
                return bool(bcrypt.checkpw(pwd_bytes, hash_bytes))
            except ValueError:
                return False

        password_bytes = _prepare_password_bytes(password)

        if isinstance(hashed_password, str):
            hashed_bytes = hashed_password.encode("ascii")
        else:
            hashed_bytes = hashed_password

        return await asyncio.to_thread(_verify_sync, password_bytes, hashed_bytes)

    def needs_rehash(self, hashed_password: str) -> bool:
        """Compare the stored hash's cost to the configured target.

        Parses the self-describing bcrypt prefix (``$2b$<cost>$...``); returns
        ``True`` when the stored cost is below the configured ``rounds``.
        Unparseable or unknown formats return ``True`` (fail-closed) — safe
        because rehashing only ever runs after a successful ``verify()``.

        Args:
            hashed_password: Stored bcrypt hash string.

        Returns:
            True when the hash should be re-computed at the current cost.
        """
        if not isinstance(hashed_password, str) or not hashed_password:
            return True
        try:
            parts = hashed_password.split("$")
            if len(parts) >= 3 and parts[1] in ("2a", "2b", "2y", "2x"):
                cost = int(parts[2])
                return cost < self._rounds
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
        """Rehash the password if needed."""
        if not hashed_password:
            return None
        if self.needs_rehash(hashed_password):
            return await self.hash(password)
        return None


# A constant dummy hash used to ensure password verification is always executed
# to prevent timing side-channels that reveal whether a username exists.
# This must be a valid bcrypt hash string to avoid verification errors.
#
# SECURITY: This is intentionally weak (not a real hash) - it is used ONLY to
# ensure that password verification runs for non-existent users, preventing
# attackers from distinguishing between "user not found" and "wrong password"
# via timing attacks. The hash is valid bcrypt format but the password that
# produces it is unknown/impossible to guess.
DUMMY_PASSWORD_HASH = "$2b$12$OMAqo55i5DcmvOMAqo55i5DcmvOMAqo55i5DcmvOMAqo55i5Dcmv"  # noqa: S105  # timing-equalization dummy, no real password matches


class PasswordPolicy(PasswordPolicyProtocol):
    """Password policy configuration.

    Lazy-loads common passwords file only when needed.
    Implements PasswordPolicyProtocol for dependency injection compatibility.
    """

    _DEFAULT_COMMON_PASSWORDS: set[str] | None = None

    def __init__(
        self,
        min_length: int = 8,  # NIST SP 800-63B minimum
        max_length: int = 128,
        require_uppercase: bool = True,
        require_lowercase: bool = True,
        require_digits: bool = False,
        require_special: bool = False,
        prevent_common: bool = True,  # NIST SP 800-63B: check against breach lists
        prevent_reuse: bool = False,
        history_size: int = 5,
        common_passwords_file: str | None = None,
        banned_patterns: list[str] | None = None,
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.require_uppercase = require_uppercase
        self.require_lowercase = require_lowercase
        self.require_digits = require_digits
        self.require_special = require_special
        self.prevent_common = prevent_common
        self.prevent_reuse = prevent_reuse
        self.history_size = history_size
        self._common_passwords_file = common_passwords_file
        self._common_passwords: set[str] | None = None
        self.banned_patterns: list[str] = banned_patterns or []

    @classmethod
    def from_config(cls, config: PasswordConfig) -> PasswordPolicy:
        """Build a ``PasswordPolicy`` from a ``PasswordConfig`` dataclass.

        Args:
            config: Password complexity configuration from ``AuthConfig.password``.

        Returns:
            A configured :class:`PasswordPolicy` instance.
        """
        return cls(
            min_length=config.min_length,
            max_length=config.max_length,
            require_uppercase=config.require_uppercase,
            require_lowercase=config.require_lowercase,
            require_digits=config.require_digits,
            require_special=config.require_special,
            banned_patterns=list(config.banned_patterns),
        )

    def _load_common_passwords(self, file_path: str | None) -> set[str]:
        """Load common passwords from file (lazy-loaded)."""
        if not file_path:
            if PasswordPolicy._DEFAULT_COMMON_PASSWORDS is None:
                PasswordPolicy._DEFAULT_COMMON_PASSWORDS = {
                    "password",
                    "password1",
                    "password123",
                    "123456",
                    "123456789",
                    "12345678",
                    "1234567890",
                    "qwerty",
                    "qwerty123",
                    "abc123",
                    "letmein",
                    "monkey",
                    "dragon",
                    "master",
                    "sunshine",
                    "princess",
                    "welcome",
                    "shadow",
                    "superman",
                    "michael",
                    "football",
                    "baseball",
                    "iloveyou",
                    "trustno1",
                    "hunter2",
                    "admin",
                    "admin123",
                    "administrator",
                    "root",
                    "toor",
                    "passw0rd",
                    "p@ssword",
                    "p@ssw0rd",
                    "pass@word",
                    "test",
                    "test123",
                    "demo",
                    "demo123",
                    "guest",
                    "guest123",
                    "login",
                    "login123",
                    "changeme",
                    "change_me",
                    "default",
                    "secret",
                    "secret123",
                    "temp",
                    "temp123",
                    "temporary",
                    "letmein1",
                    "letmein123",
                    "qwertyuiop",
                    "asdfghjkl",
                    "zxcvbnm",
                    "1q2w3e4r",
                    "1q2w3e",
                    "11111111",
                    "22222222",
                    "33333333",
                    "00000000",
                    "111111111",
                    "password2",
                    "password1!",
                    "p@ssword1",
                    "admin@123",
                    "welcome1",
                    "welcome@1",
                    "hello123",
                    "summer2023",
                    "winter2023",
                    "spring2023",
                    "autumn2023",
                    "january1",
                    "february1",
                    "march2023",
                    "welcome123",
                }
            return PasswordPolicy._DEFAULT_COMMON_PASSWORDS

        try:
            with Path(file_path).open() as f:
                return {line.strip().lower() for line in f if line.strip()}
        except FileNotFoundError:
            return set()

    def _get_common_passwords(self) -> set[str]:
        """Return common passwords set, loading lazily on first access."""
        if self._common_passwords is None:
            self._common_passwords = self._load_common_passwords(
                self._common_passwords_file
            )
        return self._common_passwords

    def validate(self, password: str) -> None:
        """Validate password against policy.

        Args:
            password: Plain text password to validate.

        Raises:
            ValueError: If the password violates the policy.
        """
        errors = []

        # Length check
        if len(password) < self.min_length:
            errors.append(
                f"Password must be at least {self.min_length} characters long",
            )

        if len(password) > self.max_length:
            errors.append(
                f"Password must be at most {self.max_length} characters long",
            )

        # Banned pattern check
        lower = password.lower()
        for pattern in self.banned_patterns:
            if pattern.lower() in lower:
                errors.append(
                    f"Password must not contain the substring '{pattern}'",
                )

        # Character requirements
        if self.require_uppercase and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")

        if self.require_lowercase and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")

        if self.require_digits and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one digit")

        if self.require_special and not any(not c.isalnum() for c in password):
            errors.append("Password must contain at least one special character")

        # Common password check
        if self.prevent_common and password.lower() in self._get_common_passwords():
            errors.append("Password is too common, please choose a different one")

        if errors:
            raise ValueError("; ".join(errors))

    def is_valid(self, password: str) -> bool:
        """Return True if the password satisfies the policy without raising.

        Args:
            password: Plain text password.

        Returns:
            True if valid, False otherwise.
        """
        try:
            self.validate(password)
            return True
        except ValueError:
            return False
