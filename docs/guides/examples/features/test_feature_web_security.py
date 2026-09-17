"""Feature tour: web perimeter — articulated doors, explicit guest lists.

Three layers cover an API surface without a single line of middleware code.
CORS is an allow-list contract: a configured origin receives a negotiated
preflight answer (204 plus echoed allow headers, credentials included), a
stranger receives a refusal, and with no origins configured the framework
stays silent — silence is the denial, browsers block what no header
blesses. Host validation only runs when ``allowed_hosts`` names its guest
list, so development stays friction-free while production keeps every
impostor out by name. Security headers are on by default the moment a
``SecurityConfig`` is present: nosniff, frame DENY and friends ride along
on every response.
"""

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, get
from quadkit.web.config.top_level import WebConfig
from quadkit.web.security.config.cors import CORSConfig
from quadkit.web.security.config.top_level import SecurityConfig

ORIGIN = "https://shop.example"


class Hello(Controller):
    @get("/hi")
    async def hi(self) -> str:
        return "hello"


def make_app(cors: CORSConfig | None = None, hosts: list[str] | None = None) -> Application:
    config = WebConfig(
        cors=cors if cors is not None else CORSConfig(),
        security=SecurityConfig(
            allowed_hosts=hosts if hosts is not None else [],
            enable_csrf=False,
        ),
    )
    app = Application()
    app.add_module(WebModule.configure(controllers=[Hello], web_config=config))
    return app


@pytest.mark.asyncio
async def test_cors_negotiates_allow_listed_origins_and_refuses_strangers() -> None:
    app = make_app(cors=CORSConfig(allowed_origins=[ORIGIN], allow_credentials=True))
    async with WebTestBed(app) as bed:
        preflight = bed.client.options(
            "/hi",
            headers={
                "Origin": ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        # A guest on the list gets a negotiated answer to their preflight.
        assert preflight.status_code == 204
        assert preflight.headers["access-control-allow-origin"] == ORIGIN
        assert preflight.headers["access-control-allow-credentials"] == "true"
        assert "GET" in preflight.headers["access-control-allow-methods"]

        # A stranger's preflight never reaches routing.
        stranger = bed.client.options(
            "/hi",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert (
            stranger.status_code != 204
        ), "unlisted origins must not receive a negotiated preflight"
        assert "access-control-allow-origin" not in stranger.headers

        # On plain requests the blessing rides along for the listed origin.
        response = bed.get("/hi", headers={"Origin": ORIGIN})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ORIGIN


@pytest.mark.asyncio
async def test_cors_silence_is_denial_when_no_origins_are_configured() -> None:
    async with WebTestBed(make_app()) as bed:
        response = bed.get("/hi", headers={"Origin": "https://anyone.example"})
        assert response.status_code == 200
        # No allow header is emitted, so the browser blocks the response
        # from a cross-origin script — the door simply never looks open.
        assert "access-control-allow-origin" not in response.headers

        preflight = bed.client.options(
            "/hi",
            headers={
                "Origin": "https://anyone.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in preflight.headers


@pytest.mark.asyncio
async def test_security_headers_are_default_and_hosts_checked_when_listed() -> None:
    async with WebTestBed(make_app()) as bed:
        response = bed.get("/hi")
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert "strict-origin" in response.headers["referrer-policy"]
        assert "permissions-policy" in response.headers

    # Host validation joins in as soon as the guest list is named.
    async with WebTestBed(make_app(hosts=["testserver"])) as bed:
        impostor = bed.client.get("/hi", headers={"Host": "admin.evil.example"})
        assert impostor.status_code == 400
        honest = bed.client.get("/hi", headers={"Host": "testserver"})
        assert honest.status_code == 200
