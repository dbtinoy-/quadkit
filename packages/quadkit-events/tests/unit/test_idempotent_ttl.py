"""TTL, isolation, and lifecycle tests for the idempotent() decorator."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from quadkit.domain import DomainModel
from quadkit.events.decorators import clear_idempotency_cache, idempotent
from quadkit.events.decorators.idempotency_cache import IdempotencyCache
from quadkit.primitives import clock as ambient_clock
from quadkit.testing.clock import FixedClock

START = datetime(2026, 8, 18, 12, 0, 0, tzinfo=UTC)


@dataclass
class TestCommand(DomainModel):
    """Minimal command with an explicit idempotency key."""

    __test__ = False

    request_id: str
    data: str


class TestIdempotentTTL:
    """The ttl parameter is honored: entries expire and the handler reruns."""

    def setup_method(self) -> None:
        clear_idempotency_cache()

    def test_entry_within_ttl_not_reexecuted(self) -> None:
        call_count = 0

        @idempotent(key_func=lambda cmd: cmd.request_id, ttl=3600)
        def handler(command: TestCommand) -> str:
            nonlocal call_count
            call_count += 1
            return f"processed: {command.data}"

        cmd = TestCommand(request_id="req-1", data="test")
        fixed = FixedClock(START)
        with ambient_clock.use(fixed):
            assert handler(cmd) == "processed: test"
            assert handler(cmd) == "processed: test"
            assert call_count == 1

    def test_entry_reexecuted_after_ttl_elapses(self) -> None:
        call_count = 0

        @idempotent(key_func=lambda cmd: cmd.request_id, ttl=60)
        def handler(command: TestCommand) -> str:
            nonlocal call_count
            call_count += 1
            return f"processed: {command.data}"

        cmd = TestCommand(request_id="req-1", data="test")
        fixed = FixedClock(START)
        with ambient_clock.use(fixed):
            assert handler(cmd) == "processed: test"
            assert handler(cmd) == "processed: test"
            assert call_count == 1
            fixed.advance(61)
            assert handler(cmd) == "processed: test"
            assert call_count == 2


class TestIdempotentCacheIsolation:
    """Each decorator application gets its own cache (no process-wide state)."""

    def setup_method(self) -> None:
        clear_idempotency_cache()

    def test_default_cache_is_per_function(self) -> None:
        a_calls = 0
        b_calls = 0

        @idempotent(key_func=lambda cmd: cmd.request_id)
        def handler_a(command: TestCommand) -> str:
            nonlocal a_calls
            a_calls += 1
            return f"a: {command.data}"

        @idempotent(key_func=lambda cmd: cmd.request_id)
        def handler_b(command: TestCommand) -> str:
            nonlocal b_calls
            b_calls += 1
            return f"b: {command.data}"

        cmd = TestCommand(request_id="req-1", data="x")
        handler_a(cmd)
        handler_b(cmd)
        assert a_calls == 1
        assert b_calls == 1

    def test_explicit_cache_instance_shares_state(self) -> None:
        a_calls = 0
        b_calls = 0
        shared = IdempotencyCache()

        @idempotent(key_func=lambda cmd: cmd.request_id, cache=shared)
        def handler_a(command: TestCommand) -> str:
            nonlocal a_calls
            a_calls += 1
            return f"a: {command.data}"

        @idempotent(key_func=lambda cmd: cmd.request_id, cache=shared)
        def handler_b(command: TestCommand) -> str:
            nonlocal b_calls
            b_calls += 1
            return "unreachable"

        cmd = TestCommand(request_id="req-1", data="x")
        handler_a(cmd)
        handler_b(cmd)
        assert a_calls == 1
        assert b_calls == 0

    def test_clear_idempotency_cache_releases_all_decorated_functions(self) -> None:
        a_calls = 0
        b_calls = 0

        @idempotent(key_func=lambda cmd: cmd.request_id)
        def handler_a(command: TestCommand) -> str:
            nonlocal a_calls
            a_calls += 1
            return f"a: {command.data}"

        @idempotent(key_func=lambda cmd: cmd.request_id)
        def handler_b(command: TestCommand) -> str:
            nonlocal b_calls
            b_calls += 1
            return f"b: {command.data}"

        cmd = TestCommand(request_id="req-1", data="x")
        handler_a(cmd)
        handler_b(cmd)
        assert a_calls == 1
        assert b_calls == 1
        clear_idempotency_cache()
        handler_a(cmd)
        handler_b(cmd)
        assert a_calls == 2
        assert b_calls == 2


class TestIdempotentFidelity:
    """Result caching semantics match the pre-fix behavior."""

    def setup_method(self) -> None:
        clear_idempotency_cache()

    def test_cached_none_result_not_reexecuted(self) -> None:
        call_count = 0

        @idempotent(key_func=lambda cmd: cmd.request_id)
        def handler(command: TestCommand) -> None:
            nonlocal call_count
            call_count += 1

        cmd = TestCommand(request_id="req-1", data="x")
        handler(cmd)
        handler(cmd)
        assert call_count == 1

    def test_no_module_level_cache_dict(self) -> None:
        import quadkit.events.decorators.validation as validation_module

        assert not hasattr(validation_module, "_idempotency_cache")
