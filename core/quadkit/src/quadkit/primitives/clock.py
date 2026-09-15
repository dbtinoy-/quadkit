"""Clock primitive — process-wide UTC time and monotonic source.

The clock is a stateless, stdlib-backed primitive. There is no ClockConfig,
no ClockProvider, no DI registration: a single SystemClock implementation
backs the ambient API by default, and tests override via use() / install().

For type-hinting opt-in injection (rare), import ClockProtocol from
quadkit-contracts.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import contextvars
from datetime import UTC, datetime
import time

from quadkit.contracts.core.clock import ClockProtocol


class _SystemClock:
    """Default UTC clock backed by stdlib datetime/time."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()

    def timestamp(self) -> float:
        return time.time()

    def time(self) -> float:
        return time.time()


_ambient: contextvars.ContextVar[ClockProtocol] = contextvars.ContextVar[ClockProtocol](
    "quadkit_clock",
    default=_SystemClock(),  # noqa: B039
)


def install(implementation: ClockProtocol) -> None:
    """Install a process-wide clock. Idempotent; last call wins."""
    _ambient.set(implementation)


def current() -> ClockProtocol:
    """Return the active clock (rarely needed by callers)."""
    return _ambient.get()


def now() -> datetime:
    return _ambient.get().now()


def monotonic() -> float:
    return _ambient.get().monotonic()


def timestamp() -> float:
    return _ambient.get().timestamp()


@contextmanager
def use(implementation: ClockProtocol) -> Iterator[None]:
    """Override the ambient clock for the duration of a block."""
    token = _ambient.set(implementation)
    try:
        yield
    finally:
        _ambient.reset(token)


__all__ = ["current", "install", "monotonic", "now", "timestamp", "use"]
