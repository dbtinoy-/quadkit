"""Tests for SSE backpressure, retry tracking, connection events, and SSEResponse."""

from __future__ import annotations

import pytest

from quadkit.web.sse.backpressure import (
    SSEBackpressureHandler,
    SSEConnectionEvents,
    SSEResponse,
    SSERetryTracker,
)


class TestBackpressureHandler:
    async def test_lazy_queue(self) -> None:
        h = SSEBackpressureHandler(max_buffer_size=7)
        assert h._queue is None  # noqa: SLF001
        assert h.queue.maxsize == 7  # noqa: SLF001
        assert h.queue is h.queue  # idempotent

    async def test_send_returns_true_and_stores(self) -> None:
        h = SSEBackpressureHandler(max_buffer_size=10)
        assert await h.send("message", "hello", "e1") is True
        msg = await h.queue.get()
        assert msg == {"event": "message", "data": "hello", "id": "e1"}

    async def test_send_without_id_omits_key(self) -> None:
        h = SSEBackpressureHandler(max_buffer_size=10)
        await h.send("message", "x")
        msg = await h.queue.get()
        assert "id" not in msg

    async def test_send_backpressure_when_full(self) -> None:
        h = SSEBackpressureHandler(max_buffer_size=2)
        assert await h.send("a", "1") is True
        assert await h.send("a", "2") is True
        assert await h.send("a", "3") is False  # buffer full

    async def test_send_after_close_returns_false(self) -> None:
        h = SSEBackpressureHandler()
        h.close()
        assert await h.send("a", "1") is False

    async def test_events_yields_and_stops_on_close(self) -> None:
        h = SSEBackpressureHandler()
        await h.send("message", "one")

        async def collect() -> list[dict]:
            out = []
            async for ev in h.events():
                out.append(ev)
                if len(out) == 1:
                    h.close()
            return out

        events = await collect()
        assert events == [{"event": "message", "data": "one"}]

    async def test_wait_for_space_times_out_when_full(self) -> None:
        h = SSEBackpressureHandler(max_buffer_size=1)
        await h.send("a", "1")
        assert await h.wait_for_space(timeout=0.05) is False

    async def test_close_sets_flag(self) -> None:
        h = SSEBackpressureHandler()
        assert h._closed is False  # noqa: SLF001
        h.close()
        assert h._closed is True  # noqa: SLF001


class TestRetryTracker:
    def test_last_event_id_default_none(self) -> None:
        t = SSERetryTracker()
        assert t.last_event_id is None

    def test_set_last_event_id(self) -> None:
        t = SSERetryTracker()
        t.set_last_event_id("e5")
        assert t.last_event_id == "e5"

    def test_record_event_updates_and_stores(self) -> None:
        t = SSERetryTracker()
        t.record_event("1", "message", "a")
        t.record_event("2", "message", "b")
        assert t.last_event_id == "2"
        assert t._event_history["1"] == {"event": "message", "data": "a", "id": "1"}  # noqa: SLF001

    def test_get_events_after(self) -> None:
        t = SSERetryTracker()
        for i in range(1, 5):
            t.record_event(str(i), "message", f"d{i}")
        after = t.get_events_after("2")
        assert [e["id"] for e in after] == ["3", "4"]

    def test_get_events_after_missing_id(self) -> None:
        t = SSERetryTracker()
        t.record_event("1", "message", "a")
        assert t.get_events_after("nope") == []

    def test_history_trimmed_to_max(self) -> None:
        t = SSERetryTracker()
        t._max_history = 3  # noqa: SLF001
        for i in range(1, 7):
            t.record_event(str(i), "message", "x")
        assert len(t._event_history) == 3  # noqa: SLF001
        # oldest entries (1,2,3,4) dropped; 5 and 6 remain
        assert "1" not in t._event_history  # noqa: SLF001
        assert "6" in t._event_history  # noqa: SLF001


class TestConnectionEvents:
    async def test_no_callbacks_noop(self) -> None:
        e = SSEConnectionEvents()
        await e.fire_connect()
        await e.fire_disconnect()
        await e.fire_error(RuntimeError("x"))  # must not raise

    async def test_sync_callbacks(self) -> None:
        calls: list[str] = []
        e = SSEConnectionEvents(
            on_connect=lambda: calls.append("connect"),
            on_disconnect=lambda: calls.append("disconnect"),
            on_error=lambda err: calls.append(f"error:{err}"),
        )
        await e.fire_connect()
        await e.fire_error(RuntimeError("boom"))
        await e.fire_disconnect()
        assert calls == ["connect", "error:boom", "disconnect"]

    async def test_async_callbacks(self) -> None:
        calls: list[str] = []

        async def on_connect() -> None:
            calls.append("connect")

        async def on_error(err: Exception) -> None:
            calls.append(f"error:{err}")

        e = SSEConnectionEvents(on_connect=on_connect, on_error=on_error)
        await e.fire_connect()
        await e.fire_error(ValueError("bad"))
        assert calls == ["connect", "error:bad"]

    async def test_args_forwarded(self) -> None:
        got: dict = {}

        def on_connect(req, **kw) -> None:
            got["req"] = req
            got["kw"] = kw

        e = SSEConnectionEvents(on_connect=on_connect)
        await e.fire_connect("REQ-1", reason="test")
        assert got == {"req": "REQ-1", "kw": {"reason": "test"}}


class TestSSEResponse:
    async def test_stream_formats_events(self) -> None:
        async def gen():
            yield {"event": "update", "data": "line1\nline2", "id": "42"}
            yield "plain"

        resp = SSEResponse(gen(), backpressure=False)
        chunks = [c async for c in resp.stream()]
        assert chunks[0] == "retry: 5000\n\n"
        update = chunks[1]
        assert update.startswith("event: update\n")
        assert "data: line1\n" in update
        assert "data: line2\n" in update
        assert "id: 42\n" in update
        assert chunks[2].startswith("event: message\n")
        assert "data: plain\n" in chunks[2]

    async def test_retry_tracker_records_ids(self) -> None:
        async def gen():
            yield {"event": "update", "data": "x", "id": "7"}

        resp = SSEResponse(gen(), backpressure=False)
        _ = [c async for c in resp.stream()]
        assert resp._retry_tracker.last_event_id == "7"  # noqa: SLF001

    async def test_backpressure_drops_full_buffer(self) -> None:
        h = SSEBackpressureHandler(max_buffer_size=1)
        await h.send("pre", "filler")

        async def gen():
            yield {"event": "drop", "data": "nope"}

        resp = SSEResponse(gen(), backpressure=True, max_buffer=1)
        # replace handler with the pre-filled one
        resp._handler = h  # noqa: SLF001
        chunks = [c async for c in resp.stream()]
        assert len(chunks) == 1  # only retry line; event dropped

    async def test_lifecycle_events_fired(self) -> None:
        calls: list[str] = []

        async def gen():
            yield "x"

        events = SSEConnectionEvents(
            on_connect=lambda: calls.append("connect"),
            on_disconnect=lambda: calls.append("disconnect"),
        )
        resp = SSEResponse(gen(), backpressure=False, events=events)
        _ = [c async for c in resp.stream()]
        assert calls == ["connect", "disconnect"]

    async def test_error_fires_and_raises(self) -> None:
        calls: list[str] = []

        async def gen():
            yield "x"
            raise RuntimeError("stream died")
            yield  # pragma: no cover

        events = SSEConnectionEvents(on_error=lambda e: calls.append(str(e)))
        resp = SSEResponse(gen(), backpressure=False, events=events)
        with pytest.raises(RuntimeError, match="stream died"):
            _ = [c async for c in resp.stream()]
        assert calls == ["stream died"]

    def test_to_response(self) -> None:
        async def gen():
            yield "x"

        resp = SSEResponse(gen())
        starlette_resp = resp.to_response()
        assert starlette_resp.media_type == "text/event-stream"
