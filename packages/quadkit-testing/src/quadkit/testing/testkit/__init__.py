"""Lightweight test utilities for unit testing Quadkit services.

Provides zero-dependency helpers for unit tests — no extension packages
required.

Exports:
    TestEnvironment: Pre-wired container with in-memory fakes for unit tests.
    FakeRepository, FakeEventBus, FakeCommandBus, FakeQueryBus,
    FakeAuditLogger, FakeLock, FakeOutbox, FakeUoW: Test-friendly aliases for memory fakes.
    assert_ok, assert_err, assert_err_type, assert_err_contains: Result helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quadkit.testing.testkit.assertions import (
        assert_err,
        assert_err_contains,
        assert_err_type,
        assert_ok,
    )
    from quadkit.testing.testkit.environment import TestEnvironment
    from quadkit.testing.testkit.fakes import (
        FakeAuditLogger,
        FakeCommandBus,
        FakeEventBus,
        FakeLock,
        FakeOutbox,
        FakeQueryBus,
        FakeRepository,
        FakeUoW,
    )

_LAZY_IMPORTS: dict[str, str] = {
    # Environment
    "TestEnvironment": "quadkit.testing.testkit.environment",
    # Fakes
    "FakeAuditLogger": "quadkit.testing.testkit.fakes",
    "FakeCommandBus": "quadkit.testing.testkit.fakes",
    "FakeEventBus": "quadkit.testing.testkit.fakes",
    "FakeLock": "quadkit.testing.testkit.fakes",
    "FakeOutbox": "quadkit.testing.testkit.fakes",
    "FakeQueryBus": "quadkit.testing.testkit.fakes",
    "FakeRepository": "quadkit.testing.testkit.fakes",
    "FakeUoW": "quadkit.testing.testkit.fakes",
    # Assertions
    "assert_err": "quadkit.testing.testkit.assertions",
    "assert_err_contains": "quadkit.testing.testkit.assertions",
    "assert_err_type": "quadkit.testing.testkit.assertions",
    "assert_ok": "quadkit.testing.testkit.assertions",
}


def __getattr__(name: str) -> object:
    """Lazily import and return a public attribute by name."""
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    """Return list of public API names."""
    return list(_LAZY_IMPORTS.keys())


__all__ = list(_LAZY_IMPORTS.keys())
