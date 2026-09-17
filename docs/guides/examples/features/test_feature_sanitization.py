"""Feature tour: input sanitization as one middleware line.

Add `InputSanitizationMiddleware` to the module's middleware list and
query-string values are scrubbed before handlers see them: null bytes
are stripped unconditionally, and obvious injection payloads
(`<script ...>`, `javascript:` URIs) are dropped to empty values.
Defense in depth — service-layer validation still applies.
"""

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, InputSanitizationMiddleware, WebModule, get, query


class SearchController(Controller):
    @get("/search")
    async def search(self, q: str = query("")) -> dict:
        return {"q": q}


def create_app() -> Application:
    app = Application()
    app.add_module(
        WebModule.configure(
            controllers=[SearchController],
            middleware=[InputSanitizationMiddleware],
        )
    )
    return app


@pytest.mark.asyncio
async def test_injection_payloads_are_dropped() -> None:
    async with WebTestBed(create_app()) as bed:
        pass_through = bed.get("/search", params={"q": "quadratics"})
        assert pass_through.json == {"q": "quadratics"}

        scripted = bed.get("/search", params={"q": "<script>alert(1)</script>"})
        assert scripted.status_code == 200
        assert scripted.json == {"q": ""}  # payload dropped, route still serves

        uri_trick = bed.get("/search", params={"q": "javascript:alert(1)"})
        assert uri_trick.json == {"q": ""}


@pytest.mark.asyncio
async def test_null_bytes_are_stripped_from_values() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/search?q=ab%00c")  # \x00 travels percent-encoded
        assert response.json == {"q": "abc"}
