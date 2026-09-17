"""Feature tour: HTMX endpoints return partials with protocol headers.

Handlers return HTML fragments, not pages. `HTMXResponse` stamps the
HTMX protocol headers for you — `hx_trigger` dicts are JSON-encoded
into `HX-Trigger` for client-side event listeners, `hx_refresh=True`
issues a full-page `HX-Refresh` — while a bare `str` return serializes
as `text/html` for free and the `HTMLContent` marker keeps rich markup
out of JSON serialization. HTMX's swap model gets exactly what it needs
from plain controller methods.
"""

import json

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, HTMLContent, HTMXResponse, WebModule, get


class BoardController(Controller):
    @get("/board/card")
    async def card(self) -> HTMXResponse:
        return HTMXResponse("<li>shipped</li>", hx_trigger={"toast": "Card saved"})

    @get("/board/ping")
    async def ping(self) -> HTMXResponse:
        # A plain string trigger travels the header verbatim.
        return HTMXResponse("<span>pong</span>", hx_trigger="board:pinged")

    @get("/board/stale")
    async def stale(self) -> HTMXResponse:
        return HTMXResponse("<p>out of date</p>", hx_refresh=True)

    @get("/board/banner")
    async def banner(self) -> str:
        return "<strong>tour</strong>"  # bare str serializes as text/html

    @get("/board/notice")
    async def notice(self) -> HTMLContent:
        return HTMLContent("<em>hello</em>")


def create_app() -> Application:
    app = Application()
    app.add_module(WebModule.configure(controllers=[BoardController]))
    return app


def lower_headers(response) -> dict[str, str]:  # type: ignore[no-untyped-def]
    return {k.lower(): v for k, v in response.headers.items()}


@pytest.mark.asyncio
async def test_hx_trigger_dict_is_json_encoded() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.get("/board/card")
        assert response.status_code == 200
        assert response.text == "<li>shipped</li>"
        headers = lower_headers(response)
        assert headers["content-type"].startswith("text/html")
        assert json.loads(headers["hx-trigger"]) == {"toast": "Card saved"}


@pytest.mark.asyncio
async def test_string_trigger_and_refresh_headers_pass_through() -> None:
    async with WebTestBed(create_app()) as bed:
        ping = lower_headers(bed.get("/board/ping"))
        assert ping["hx-trigger"] == "board:pinged"

        stale = lower_headers(bed.get("/board/stale"))
        assert stale["hx-refresh"] == "true"
        assert "hx-trigger" not in stale  # only the headers you ask for


@pytest.mark.asyncio
async def test_bare_strings_and_html_content_serve_as_html() -> None:
    async with WebTestBed(create_app()) as bed:
        banner = bed.get("/board/banner")
        assert banner.status_code == 200
        assert banner.text == "<strong>tour</strong>"
        assert lower_headers(banner)["content-type"].startswith("text/html")

        notice = bed.get("/board/notice")
        assert notice.text == "<em>hello</em>"
        assert lower_headers(notice)["content-type"].startswith("text/html")
