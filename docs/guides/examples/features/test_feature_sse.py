"""Feature tour: Server-Sent Events.

A controller streams events to the browser with `EventSourceResponse` —
each `ServerSentEvent` is typed (data, event name, id, retry), the
framework handles framing and heartbeats. No hand-rolled response
plumbing in user code.
"""

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, get
from quadkit.web.sse import (
    EventSourceResponse,
    ServerSentEvent,
    SSEConnectionEvents,
    SSEResponse,
)


class FeedController(Controller):
    @get("/feed")
    async def feed(self):
        async def events():
            for i, word in enumerate(["async", "contract-driven", "container-assembled"]):
                yield ServerSentEvent(data={"step": word, "n": i}, event="word", event_id=str(i))

        return EventSourceResponse(events())


def create_app() -> Application:
    app = Application()
    app.add_modules([WebModule.configure(controllers=[FeedController])])
    return app


@pytest.mark.asyncio
async def test_sse_stream_delivers_all_events():
    async with WebTestBed(create_app()) as bed:
        response = bed.client.get("/feed")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.text
        assert "event: word" in body
        for word in ("async", "contract-driven", "container-assembled"):
            assert word in body


lifecycle: list[str] = []


class AdvancedFeedController(Controller):
    @get("/advanced-feed")
    async def advanced_feed(self):
        async def events():
            yield {"data": "order-1 received", "event": "order", "id": "evt-1"}
            yield {"data": "order-1 shipped", "event": "order", "id": "evt-2"}

        return SSEResponse(
            events(),
            retry_timeout=1234,
            events=SSEConnectionEvents(
                on_connect=lambda: lifecycle.append("connected"),
                on_disconnect=lambda: lifecycle.append("disconnected"),
            ),
        ).to_response()


@pytest.mark.asyncio
async def test_advanced_sse_retry_ids_and_lifecycle():
    """SSEResponse adds retry directives, dict-event ids, and connect/disconnect hooks."""
    lifecycle.clear()

    app = Application()
    app.add_module(WebModule.configure(controllers=[AdvancedFeedController]))

    async with WebTestBed(app) as bed:
        response = bed.get("/advanced-feed")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = response.text

        # The retry directive is always the first frame the client sees.
        assert body.startswith("retry: 1234\n\n")

        # Dict events carry typed names and durable ids.
        assert "event: order\n" in body
        assert "id: evt-1\n" in body
        assert "id: evt-2\n" in body
        assert "data: order-1 received\n" in body
        assert "data: order-1 shipped\n" in body

        # Connection lifecycle callbacks fired around the whole stream.
        assert lifecycle == ["connected", "disconnected"]
