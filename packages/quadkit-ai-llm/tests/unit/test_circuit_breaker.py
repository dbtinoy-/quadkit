"""Round-55/57 pins: provider circuit breaker state machine.

``ProviderCircuitBreaker`` sits in the failure path of every LLM client
(``clients/base.py``) and in the routing fallback chain.  These tests
pin the exact transition semantics: CLOSED → OPEN at the failure
threshold, OPEN blocks until the timeout elapses, OPEN → HALF_OPEN
admits **at most one probe request at a time** (Round 57: concurrent
callers are blocked while a probe is in flight), a **failed probe
re-opens the circuit immediately**, HALF_OPEN closes after
``success_threshold`` successful probes, and ``reset`` returns the
breaker to its initial state.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from quadkit.ai.llm.health import (
    CircuitBreakerConfig,
    CircuitState,
    ProviderCircuitBreaker,
)


def _breaker(
    failure_threshold: int = 5,
    success_threshold: int = 2,
    timeout_seconds: int = 60,
) -> ProviderCircuitBreaker:
    return ProviderCircuitBreaker(
        "test-provider",
        CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout_seconds=timeout_seconds,
        ),
    )


def _failures(exc: Exception | None = None) -> Exception:
    return exc if exc is not None else RuntimeError("boom")


async def _open(breaker: ProviderCircuitBreaker) -> None:
    """Drive the breaker CLOSED → OPEN via the public failure path."""
    for _ in range(breaker.config.failure_threshold):
        await breaker.record_failure(_failures())
    assert breaker.state is CircuitState.OPEN


def _age_out(breaker: ProviderCircuitBreaker) -> None:
    """Push ``opened_at`` past the open timeout."""
    breaker.opened_at = datetime.now(UTC) - timedelta(
        seconds=breaker.config.timeout_seconds + 1
    )


async def _half_open(breaker: ProviderCircuitBreaker) -> None:
    """Drive the breaker to HALF_OPEN and assert the probe is admitted."""
    await _open(breaker)
    _age_out(breaker)
    assert await breaker.is_available() is True
    assert breaker.state is CircuitState.HALF_OPEN


class TestCircuitBreakerConfig:
    def test_defaults(self) -> None:
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout_seconds == 60
        assert config.window_size == 20

    def test_initial_state_is_closed_and_available(self) -> None:
        breaker = _breaker()
        assert breaker.state is CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
        assert breaker.opened_at is None
        assert breaker.request_times == []


class TestClosedState:
    @pytest.mark.asyncio
    async def test_success_keeps_closed_and_resets_failure_count(self) -> None:
        breaker = _breaker()
        await breaker.record_failure(_failures())
        await breaker.record_failure(_failures())
        assert breaker.failure_count == 2
        await breaker.record_success()
        assert breaker.failure_count == 0
        assert breaker.state is CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_stays_closed_below_failure_threshold(self) -> None:
        breaker = _breaker(failure_threshold=3)
        for _ in range(2):
            await breaker.record_failure(_failures())
        assert breaker.state is CircuitState.CLOSED
        assert await breaker.is_available() is True

    @pytest.mark.asyncio
    async def test_opens_exactly_at_failure_threshold(self) -> None:
        breaker = _breaker(failure_threshold=3)
        for _ in range(3):
            await breaker.record_failure(_failures())
        assert breaker.state is CircuitState.OPEN
        assert breaker.opened_at is not None


class TestOpenState:
    @pytest.mark.asyncio
    async def test_open_blocks_requests(self) -> None:
        breaker = _breaker()
        await _open(breaker)
        assert await breaker.is_available() is False

    @pytest.mark.asyncio
    async def test_open_stays_open_before_timeout(self) -> None:
        breaker = _breaker(timeout_seconds=3600)
        await _open(breaker)
        assert await breaker.is_available() is False
        assert breaker.state is CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_failures_do_not_reopen_an_open_circuit(self) -> None:
        breaker = _breaker()
        await _open(breaker)
        opened_at = breaker.opened_at
        await breaker.record_failure(_failures())
        assert breaker.state is CircuitState.OPEN
        # A single failure while OPEN must not refresh the open timestamp.
        assert breaker.opened_at == opened_at

    @pytest.mark.asyncio
    async def test_success_does_not_close_an_open_circuit(self) -> None:
        breaker = _breaker()
        await _open(breaker)
        await breaker.record_success()
        assert breaker.state is CircuitState.OPEN
        assert await breaker.is_available() is False


class TestHalfOpenState:
    @pytest.mark.asyncio
    async def test_timeout_elapse_transitions_to_half_open(self) -> None:
        breaker = _breaker()
        await _open(breaker)
        _age_out(breaker)
        assert await breaker.is_available() is True
        assert breaker.state is CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_half_open_closes_after_success_threshold(self) -> None:
        breaker = _breaker(success_threshold=2)
        await _half_open(breaker)
        await breaker.record_success()
        assert breaker.state is CircuitState.HALF_OPEN
        await breaker.record_success()
        assert breaker.state is CircuitState.CLOSED
        assert breaker.opened_at is None
        assert await breaker.is_available() is True

    @pytest.mark.asyncio
    async def test_half_open_single_success_below_threshold(self) -> None:
        breaker = _breaker(success_threshold=3)
        await _half_open(breaker)
        await breaker.record_success()
        assert breaker.state is CircuitState.HALF_OPEN
        assert breaker.success_count == 1

    @pytest.mark.asyncio
    async def test_half_open_failed_probe_reopens_immediately(self) -> None:
        breaker = _breaker(failure_threshold=5, success_threshold=1)
        await _half_open(breaker)
        # A single failed probe re-opens immediately — no need to
        # re-accumulate the failure threshold against a dead provider.
        await breaker.record_failure(_failures())
        assert breaker.state is CircuitState.OPEN
        assert breaker.opened_at is not None
        assert await breaker.is_available() is False

    @pytest.mark.asyncio
    async def test_half_open_allows_single_probe_at_a_time(self) -> None:
        breaker = _breaker(success_threshold=2)
        await _half_open(breaker)  # first caller admitted as probe
        # Concurrent callers are blocked while the probe is in flight.
        assert await breaker.is_available() is False
        # Probe resolves: the next caller may take the next probe slot.
        await breaker.record_success()
        assert breaker.state is CircuitState.HALF_OPEN
        assert await breaker.is_available() is True

    @pytest.mark.asyncio
    async def test_open_reentry_after_failed_probe(self) -> None:
        """Full cycle: open → probe → fail → open → probe → succeed."""
        breaker = _breaker(failure_threshold=2, success_threshold=1, timeout_seconds=0)
        await _open(breaker)
        # timeout_seconds=0: the very next check transitions to HALF_OPEN.
        assert await breaker.is_available() is True
        assert breaker.state is CircuitState.HALF_OPEN
        await breaker.record_failure(_failures())
        assert breaker.state is CircuitState.OPEN
        assert await breaker.is_available() is True  # re-probe after timeout
        await breaker.record_success()
        assert breaker.state is CircuitState.CLOSED
        assert await breaker.is_available() is True


class TestResetAndWindow:
    @pytest.mark.asyncio
    async def test_reset_returns_to_initial_state(self) -> None:
        breaker = _breaker()
        await _open(breaker)
        breaker.reset()
        assert breaker.state is CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
        assert breaker.last_failure_time is None
        assert breaker.opened_at is None
        assert breaker.request_times == []
        assert breaker._probe_in_flight is False
        assert await breaker.is_available() is True

    @pytest.mark.asyncio
    async def test_request_window_pruned_on_success(self) -> None:
        breaker = _breaker(timeout_seconds=60)
        stale = datetime.now(UTC) - timedelta(seconds=120)
        fresh = datetime.now(UTC) - timedelta(seconds=1)
        breaker.request_times = [stale, fresh]
        await breaker.record_success()
        assert stale not in breaker.request_times
        assert fresh in breaker.request_times

    def test_circuit_state_values(self) -> None:
        # The state values are log/metrics payloads — pin the wire form.
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"
