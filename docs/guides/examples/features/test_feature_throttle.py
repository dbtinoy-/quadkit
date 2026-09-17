"""Feature tour: rate limiting.

`RateLimitModule.configure(backend="memory")` wires the sliding-window
backend; `@throttle("2/minute")` then guards one route — declarative,
per-route, and testable without sleeping.
"""

import pytest
from starlette.requests import Request

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, RateLimitModule, WebModule, get, throttle


class ApiController(Controller):
    @get("/limited")
    @throttle("2/minute", by="ip")
    async def limited(self, request: Request) -> dict:
        return {"ok": True}

    @get("/open")
    async def open(self) -> dict:
        return {"ok": True}


def create_app() -> Application:
    app = Application()
    app.add_modules([
        WebModule.configure(controllers=[ApiController]),
        RateLimitModule.configure(backend="memory"),
    ])
    return app


@pytest.mark.asyncio
async def test_throttled_route_rejects_after_budget():
    async with WebTestBed(create_app()) as bed:
        assert bed.get("/limited").status_code == 200
        assert bed.get("/limited").status_code == 200
        third = bed.get("/limited")
        assert third.status_code == 429
        assert third.headers["retry-after"] == "60"
        body = third.json
        assert body["type"] == "urn:quadkit:too-many-requests"
        assert body["title"] == "Too Many Requests"

        # The unthrottled sibling route is untouched.
        assert bed.get("/open").status_code == 200
