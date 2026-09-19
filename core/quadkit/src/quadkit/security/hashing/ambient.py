"""Ambient hashing subsystem.

Provides process-wide content hashing via ContextVar.
Use `from quadkit import hashing` for ambient hashing.

Example:
    from quadkit import hashing

    digest = hashing.hash_hex("hello world")
    is_valid = hashing.verify_hex("hello world", "abc123...")

For tests:
    from quadkit import hashing
    from quadkit.security.hashing.digest import Sha256Hasher

    mock = MockHasher(return_value="mock-digest")
    with hashing.use(mock):
        assert hashing.hash_hex("test") == "mock-digest"
"""

from __future__ import annotations  # noqa: I001

import contextvars

from collections.abc import Iterator
from contextlib import contextmanager

from quadkit.contracts.security.protocols import HasherProtocol
from quadkit.security.hashing.digest import Sha256Hasher

_ambient: contextvars.ContextVar[HasherProtocol]

try:
    from contextvars import ContextVar

    _ambient = ContextVar[HasherProtocol](
        "quadkit_hashing",
        default=Sha256Hasher(),  # noqa: B039
    )
except ImportError:

    class _FallbackContextVar:
        _value: HasherProtocol = Sha256Hasher()

        def set(self, value: HasherProtocol) -> HasherProtocol:
            self._value = value
            return value

        def get(self, default: HasherProtocol | None = None) -> HasherProtocol:
            return self._value

    _FallbackContextVar.__name__ = "FallbackContextVar"
    _ambient = _FallbackContextVar()  # type: ignore[assignment]


def install(implementation: HasherProtocol) -> None:
    """Set the process-wide ambient hasher.

    Called once by CoreProvider.boot() after resolving the implementation.

    Args:
        implementation: The HasherProtocol implementation to use.
    """
    _ambient.set(implementation)


def hash_hex(data: str | bytes) -> str:
    """Hash data and return hex digest.

    Args:
        data: String or bytes to hash.

    Returns:
        Hex-encoded digest string.
    """
    return _ambient.get().digest(data)


def hash_bytes(data: str | bytes) -> bytes:
    """Hash data and return raw bytes.

    Args:
        data: String or bytes to hash.

    Returns:
        Raw digest bytes.
    """
    hasher = _ambient.get()
    hex_digest = hasher.digest(data)
    import binascii

    return binascii.unhexlify(hex_digest)


def verify_hex(data: str | bytes, expected: str) -> bool:
    """Verify data against expected hex digest.

    Args:
        data: String or bytes to verify.
        expected: Expected hex digest.

    Returns:
        True if match, False otherwise.
    """
    return _ambient.get().verify_digest(data, expected)


@contextmanager
def use(implementation: HasherProtocol) -> Iterator[None]:
    """Override the ambient hasher for the duration of a block.

    Used by tests. Stacks correctly under nested calls.

    Args:
        implementation: The HasherProtocol implementation to use temporarily.
    """
    token = _ambient.set(implementation)
    try:
        yield
    finally:
        _ambient.reset(token)


__all__ = [
    "hash_bytes",
    "hash_hex",
    "install",
    "use",
    "verify_hex",
]
