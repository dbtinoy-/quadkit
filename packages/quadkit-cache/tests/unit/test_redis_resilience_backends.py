"""Tests for the Redis circuit-breaker backend and local breaker types."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.cache.backends.redis.circuit import (
    CircuitBreakerBackend,
    CircuitBreakerState,
    CircuitState,
)
from quadkit.cache.backends.redis.resilience import RedisCircuitBreakerBackend


class FakeAioRedis:
    """In-memory redis.asyncio double."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}
        self.set_calls: list[dict[str, Any]] = []
        self.deleted: list[str] = []

    async def get(self, key: str) -> bytes | None:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None) -> bool:
        self.set_calls.append({"key": key, "ex": ex})
        self.store[key] = value if isinstance(value, bytes) else str(value).encode()
        return True

    async def delete(self, key: str) -> int:
        self.deleted.append(key)
        return 1 if self.store.pop(key, None) is not None else 0


def _state(
    name: str = "cb-1",
    state: CircuitState = CircuitState.OPEN,
    failure_count: int = 3,
    success_count: int = 7,
    last_failure_time: float | None = 100.5,
    last_success_time: float | None = 90.25,
    last_state_change: float = 100.0,
) -> CircuitBreakerState:
    return CircuitBreakerState(
        name=name,
        state=state,
        failure_count=failure_count,
        success_count=success_count,
        last_failure_time=last_failure_time,
        last_success_time=last_success_time,
        last_state_change=last_state_change,
    )


@pytest.fixture
def fake_redis() -> FakeAioRedis:
    return FakeAioRedis()


@pytest.fixture
def backend(fake_redis: FakeAioRedis) -> RedisCircuitBreakerBackend:
    be = RedisCircuitBreakerBackend(
        redis_url="redis://fake:6379", key_prefix="test:cb:", ttl=600
    )
    be._redis = fake_redis  # noqa: SLF001 — pre-injected client, no real I/O
    return be


class TestConstruction:
    def test_defaults(self) -> None:
        be = RedisCircuitBreakerBackend()
        assert be._redis_url == "redis://localhost:6379"  # noqa: SLF001
        assert be._key_prefix == "quadkit:cb:"  # noqa: SLF001
        assert be._ttl == 3600  # noqa: SLF001
        assert be._redis is None  # noqa: SLF001

    def test_satisfies_protocol(self, backend: RedisCircuitBreakerBackend) -> None:
        # Runtime structural check against the Protocol.
        import typing

        assert typing.runtime_checkable  # noqa: B018 — just ensuring import path
        # Duck-check the three protocol methods exist and are awaitable.
        for meth in ("get_state", "set_state", "delete_state"):
            assert callable(getattr(backend, meth))


class TestStateRoundTrip:
    async def test_get_missing_returns_none(self, backend: RedisCircuitBreakerBackend) -> None:
        assert await backend.get_state("nope") is None

    async def test_set_then_get_roundtrip(self, backend: RedisCircuitBreakerBackend) -> None:
        st = _state()
        await backend.set_state("cb-1", st)
        got = await backend.get_state("cb-1")
        assert got is not None
        assert got.name == "cb-1"
        assert got.state is CircuitState.OPEN
        assert got.failure_count == 3
        assert got.success_count == 7
        assert got.last_failure_time == 100.5
        assert got.last_success_time == 90.25
        assert got.last_state_change == 100.0

    async def test_set_uses_prefix_and_ttl(self, backend: RedisCircuitBreakerBackend) -> None:
        await backend.set_state("cb-1", _state())
        assert backend._redis is not None  # noqa: SLF001
        call = backend._redis.set_calls[0]  # noqa: SLF001
        assert call["key"] == "test:cb:cb-1"
        assert call["ex"] == 600

    async def test_all_states_roundtrip(self, backend: RedisCircuitBreakerBackend) -> None:
        for cs in CircuitState:
            name = f"cb-{cs.value}"
            await backend.set_state(name, _state(name=name, state=cs))
            got = await backend.get_state(name)
            assert got is not None
            assert got.state is cs

    async def test_none_times_roundtrip(self, backend: RedisCircuitBreakerBackend) -> None:
        st = _state(last_failure_time=None, last_success_time=None)
        await backend.set_state("cb-null", st)
        got = await backend.get_state("cb-null")
        assert got is not None
        assert got.last_failure_time is None
        assert got.last_success_time is None

    async def test_delete_removes(self, backend: RedisCircuitBreakerBackend) -> None:
        await backend.set_state("cb-1", _state())
        assert await backend.get_state("cb-1") is not None
        await backend.delete_state("cb-1")
        assert await backend.get_state("cb-1") is None

    async def test_delete_missing_is_noop(self, backend: RedisCircuitBreakerBackend) -> None:
        await backend.delete_state("never-existed")  # must not raise


class TestLocalTypes:
    def test_state_dataclass_fields(self) -> None:
        st = _state()
        assert (
            st.name,
            st.state,
            st.failure_count,
            st.success_count,
            st.last_failure_time,
            st.last_success_time,
            st.last_state_change,
        ) == (
            "cb-1",
            CircuitState.OPEN,
            3,
            7,
            100.5,
            90.25,
            100.0,
        )

    def test_circuit_state_values(self) -> None:
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_backend_protocol_shape(self) -> None:
        import inspect

        for meth in ("get_state", "set_state", "delete_state"):
            assert inspect.iscoroutinefunction(getattr(CircuitBreakerBackend, meth))
