"""Tests for concurrent resolution of scoped services within one Scope.

The container guarantees "same instance within this scope".  That guarantee
must hold even when two tasks resolve the same scoped service concurrently
while its (async) factory is still running — otherwise a request that does
``asyncio.gather(... )`` can hand two components two different "scoped"
instances (e.g. two DB sessions for one request).
"""

from __future__ import annotations

import asyncio

import pytest

from quadkit.di.container import Container


class _SlowScoped:
    """Scoped service with an async factory (simulates pool checkout)."""

    instances = 0

    def __init__(self) -> None:
        _SlowScoped.instances += 1


async def _slow_factory() -> _SlowScoped:
    await asyncio.sleep(0.01)
    return _SlowScoped()


class TestScopedConcurrency:
    """Concurrent scoped resolution must yield a single instance."""

    @pytest.fixture(autouse=True)
    def _reset_counter(self):
        _SlowScoped.instances = 0

    async def test_concurrent_resolve_single_instance(self):
        container = Container()
        container.scoped(_SlowScoped, _slow_factory)
        async with container.create_scope() as scope:
            a, b = await asyncio.gather(
                scope.resolve(_SlowScoped), scope.resolve(_SlowScoped)
            )
        assert a is b
        assert _SlowScoped.instances == 1

    async def test_late_resolve_hits_cache(self):
        container = Container()
        container.scoped(_SlowScoped, _slow_factory)
        async with container.create_scope() as scope:
            first = await scope.resolve(_SlowScoped)
            second = await scope.resolve(_SlowScoped)
        assert first is second
        assert _SlowScoped.instances == 1


async def _failing_factory() -> _SlowScoped:
    await asyncio.sleep(0.005)
    raise RuntimeError("factory boom")


async def _flaky_factory(attempts: dict[str, int]) -> _SlowScoped:
    attempts["n"] = attempts.get("n", 0) + 1
    if attempts["n"] == 1:
        raise RuntimeError("first attempt fails")
    return _SlowScoped()


class TestScopedConcurrencyFailure:
    """A failed creation must not poison the scope."""

    @pytest.fixture(autouse=True)
    def _reset_counter(self):
        _SlowScoped.instances = 0

    async def test_all_waiters_get_the_error(self):
        container = Container()
        container.scoped(_SlowScoped, _failing_factory)
        async with container.create_scope() as scope:
            results = await asyncio.gather(
                scope.resolve(_SlowScoped),
                scope.resolve(_SlowScoped),
                return_exceptions=True,
            )
        assert all(
            isinstance(r, RuntimeError) and "factory boom" in str(r) for r in results
        )

    async def test_scope_usable_after_failed_creation(self):
        """The in-flight slot is cleared on failure, so a later resolve retries."""
        attempts: dict[str, int] = {}
        container = Container()
        container.scoped(_SlowScoped, lambda: _flaky_factory(attempts))
        async with container.create_scope() as scope:
            with pytest.raises(RuntimeError, match="first attempt fails"):
                await scope.resolve(_SlowScoped)
            ok = await scope.resolve(_SlowScoped)
        assert isinstance(ok, _SlowScoped)
        assert _SlowScoped.instances == 1
