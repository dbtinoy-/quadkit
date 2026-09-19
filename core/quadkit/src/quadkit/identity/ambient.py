"""Ambient identity subsystem.

Provides process-wide identity generation via ContextVar.
Use `from quadkit import identity` for ambient ID generation.

Example:
    from quadkit import identity

    id = identity.generate_for("user")      # ULID/UUID based on config
    uuid = identity.new_uuid()             # Random UUID4

For tests:
    from quadkit import identity
    from quadkit.identity.generator import Uuid4Generator

    with identity.use(SeededGenerator(["id-1", "id-2"])):
        assert identity.generate_for("user") == "id-1"
"""

from __future__ import annotations  # noqa: I001

import contextvars

from collections.abc import Iterator
from contextlib import contextmanager

from quadkit.contracts.core.identity import IdGeneratorProtocol
from quadkit.identity.generator import Uuid4Generator

_ambient: contextvars.ContextVar[IdGeneratorProtocol]

try:
    from contextvars import ContextVar

    _ambient = ContextVar[IdGeneratorProtocol](
        "quadkit_identity",
        default=Uuid4Generator(),  # noqa: B039
    )
except ImportError:

    class _FallbackContextVar:
        _value: IdGeneratorProtocol = Uuid4Generator()

        def set(self, value: IdGeneratorProtocol) -> IdGeneratorProtocol:
            self._value = value
            return value

        def get(
            self, default: IdGeneratorProtocol | None = None
        ) -> IdGeneratorProtocol:
            return self._value

    _FallbackContextVar.__name__ = "FallbackContextVar"
    _ambient = _FallbackContextVar()  # type: ignore[assignment]


def install(implementation: IdGeneratorProtocol) -> None:
    """Set the process-wide ambient identity generator.

    Called once by CoreProvider.boot() after resolving the implementation.

    Args:
        implementation: The IdGeneratorProtocol implementation to use.
    """
    _ambient.set(implementation)


def generate_for(entity_type: str) -> str:
    """Generate a time-ordered ID for the given entity type.

    Args:
        entity_type: The type of entity (e.g., "user", "event", "task").

    Returns:
        A unique ID string.
    """
    return _ambient.get().generate_for(entity_type)


def new_uuid() -> str:
    """Generate a random UUID4.

    Returns:
        A random UUID4 string.
    """
    return _ambient.get().generate()


@contextmanager
def use(implementation: IdGeneratorProtocol) -> Iterator[None]:
    """Override the ambient identity generator for the duration of a block.

    Used by tests and per-request scopes. Stacks correctly under nested calls.

    Args:
        implementation: The IdGeneratorProtocol implementation to use temporarily.
    """
    token = _ambient.set(implementation)
    try:
        yield
    finally:
        _ambient.reset(token)


__all__ = [
    "generate_for",
    "install",
    "new_uuid",
    "use",
]
