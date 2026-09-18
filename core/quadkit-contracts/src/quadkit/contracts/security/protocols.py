"""Security protocol definitions for the Quadkit Framework.

Protocols for guard chains, input sanitization, and security header management.
All security implementations must satisfy these structural interfaces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.web.guard import GuardProtocol


@runtime_checkable
class HasherProtocol(Protocol):
    """General-purpose hashing protocol (non-password-specific)."""

    @property
    def algorithm(self) -> str:
        """Hash algorithm name (for example ``sha256`` or ``blake2b``)."""
        ...

    def digest(self, data: str | bytes) -> str:
        """Hash input data and return an encoded digest.

        Args:
            data: Input string or bytes to hash.

        Returns:
            Encoded hash string.
        """
        ...

    def verify_digest(self, data: str | bytes, expected: str) -> bool:
        """Constant-time verification against an expected digest.

        Args:
            data: Input string or bytes to hash.
            expected: Expected encoded digest.

        Returns:
            True when the digest matches, False otherwise.
        """
        ...

    async def hash(self, value: str) -> str:
        """Backward-compatible async alias for :meth:`digest`."""
        ...

    async def verify(self, value: str, hashed_value: str) -> bool:
        """Backward-compatible async alias for :meth:`verify_digest`."""
        ...


@runtime_checkable
class KeyDerivationProtocol(Protocol):
    """Protocol for key derivation services."""

    async def derive(self, secret: str, *, salt: bytes | None = None) -> str:
        """Derive an encoded key from a secret.

        Args:
            secret: Input secret to derive from.
            salt: Optional salt. When omitted, implementations generate one.

        Returns:
            Stable encoded key derivation string.
        """
        ...

    async def verify(self, secret: str, encoded: str) -> bool:
        """Verify a secret against a derived key payload.

        Args:
            secret: Input secret to verify.
            encoded: Stable encoded key derivation string.

        Returns:
            True when the secret matches the encoded payload, False otherwise.
        """
        ...

    async def hash(self, secret: str, *, salt: bytes | None = None) -> str:
        """Backward-compatible async alias for :meth:`derive`."""
        ...


@runtime_checkable
class GuardChainProtocol(Protocol):
    """Executes a sequence of guards; short-circuits on first denial.

    Implementations must raise ``GuardDeniedError`` from
    ``quadkit.contracts.exceptions.security`` when any guard denies.
    """

    def add(self, guard: GuardProtocol) -> GuardChainProtocol:
        """Add a guard to the chain.

        Args:
            guard: The guard to append.

        Returns:
            Self, for fluent chaining.
        """
        ...

    async def execute(self, context: dict[str, Any]) -> None:
        """Execute all guards in order, raising on first denial.

        Args:
            context: Arbitrary request context forwarded to each guard.

        Raises:
            GuardDeniedError: If any guard returns False from ``can_activate``.
        """
        ...


@runtime_checkable
class InputSanitizerProtocol(Protocol):
    """Sanitizes raw input strings against injection vectors.

    Implementations should strip XSS payloads, HTML entities, and
    dangerous character sequences without raising on clean input.
    """

    def sanitize(self, value: str) -> str:
        """Sanitize a single string value.

        Args:
            value: Raw input string.

        Returns:
            The sanitized string.
        """
        ...

    def sanitize_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively sanitize all string values in a mapping.

        Args:
            data: Dictionary whose string leaf values will be sanitized.

        Returns:
            A new dictionary with all string values sanitized.
        """
        ...

    def sanitize_header_value(self, value: str) -> str:
        """Strip CRLF characters from an HTTP header value to prevent header injection.

        Args:
            value: Raw header value string.

        Returns:
            The value with CR and LF characters removed or replaced.
        """
        ...

    def is_safe_url_for_request(self, url: str) -> bool:
        """Return False if the URL targets a private or reserved IP range (SSRF guard).

        Args:
            url: Fully-qualified URL to evaluate.

        Returns:
            True if the URL is considered safe to request, False otherwise.
        """
        ...


@runtime_checkable
class SecurityHeadersProtocol(Protocol):
    """Applies security-related HTTP response headers.

    Implementations must support HSTS, X-Frame-Options, CSP, and
    X-Content-Type-Options at minimum.
    """

    def apply(self, headers: dict[str, str]) -> dict[str, str]:
        """Apply security headers to an existing headers mapping.

        Args:
            headers: Mutable mapping of header names to values.

        Returns:
            The headers mapping with security headers merged in.
        """
        ...


@runtime_checkable
class EncryptionProtocol(Protocol):
    """Protocol for symmetric/asymmetric encryption providers."""

    async def encrypt(self, plaintext: bytes, key_id: str | None = None) -> bytes: ...
    async def decrypt(self, ciphertext: bytes, key_id: str | None = None) -> bytes: ...
    async def rotate_key(self, key_id: str) -> str: ...


@runtime_checkable
class CORSProtocol(Protocol):
    """Protocol for Cross-Origin Resource Sharing policy enforcement."""

    def is_allowed_origin(self, origin: str) -> bool: ...
    def get_allowed_headers(self) -> list[str]: ...
    def get_allowed_methods(self) -> list[str]: ...
    def get_max_age(self) -> int: ...


@runtime_checkable
class CSPProtocol(Protocol):
    """Protocol for Content Security Policy header generation."""

    def build_header(self) -> str: ...
    def add_directive(self, directive: str, value: str) -> None: ...


@runtime_checkable
class CSRFProtocol(Protocol):
    """Protocol for CSRF token generation and validation."""

    def generate_token(self, session_id: str) -> str: ...
    def validate_token(self, session_id: str, token: str) -> bool: ...
    def invalidate_token(self, session_id: str) -> None: ...


__all__ = [
    "CORSProtocol",
    "CSPProtocol",
    "CSRFProtocol",
    "EncryptionProtocol",
    "GuardChainProtocol",
    "HasherProtocol",
    "InputSanitizerProtocol",
    "KeyDerivationProtocol",
    "SecurityHeadersProtocol",
]
