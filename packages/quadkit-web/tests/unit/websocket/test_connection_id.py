"""Tests for the WebSocket ConnectionIDManager."""

from __future__ import annotations

import uuid

from quadkit.web.websocket.connection_id import ConnectionIDManager


class _WS:
    """Stand-in for a WebSocket (hashable, weakref-able)."""

    _counter = 0

    def __init__(self) -> None:
        _WS._counter += 1
        self.id = f"ws-{_WS._counter}"


class _FakeIdGenerator:
    def __init__(self) -> None:
        self.values = iter([f"gen-{i}" for i in range(100)])
        self.calls = 0

    def generate(self) -> str:
        self.calls += 1
        return next(self.values)


class TestGetOrCreate:
    def test_stable_across_calls(self) -> None:
        mgr = ConnectionIDManager()
        ws = _WS()
        first = mgr.get_or_create(ws)
        second = mgr.get_or_create(ws)
        assert first == second
        # uuid4-shaped
        uuid.UUID(first)

    def test_distinct_ids_per_websocket(self) -> None:
        mgr = ConnectionIDManager()
        a, b = _WS(), _WS()
        assert mgr.get_or_create(a) != mgr.get_or_create(b)

    def test_custom_id_generator_used(self) -> None:
        gen = _FakeIdGenerator()
        mgr = ConnectionIDManager(id_generator=gen)
        ws = _WS()
        assert mgr.get_or_create(ws) == "gen-0"
        assert gen.calls == 1
        # second call reuses, no new generation
        mgr.get_or_create(ws)
        assert gen.calls == 1


class TestGet:
    def test_unregistered_returns_none(self) -> None:
        mgr = ConnectionIDManager()
        assert mgr.get(_WS()) is None

    def test_registered_returns_id(self) -> None:
        mgr = ConnectionIDManager()
        ws = _WS()
        expected = mgr.get_or_create(ws)
        assert mgr.get(ws) == expected


class TestWeakCleanup:
    def test_entry_removed_after_gc(self) -> None:
        mgr = ConnectionIDManager()
        ws = _WS()
        cid = mgr.get_or_create(ws)
        assert mgr.get(ws) == cid
        del ws
        import gc

        gc.collect()
        assert len(mgr._ws_to_id) == 0
