"""Feature tour: version extraction — four strategies, one state key.

`@api_version` (see `test_feature_api_version.py`) mounts routes; it
says *where* versions live. `VersioningMiddleware` answers the other
question — *which* version this request is for — by extracting it from
the header, query string, URI segment, or media type per
`VersioningConfig`, and stamping `request.state.api_version` for
handlers and diagnostics. Extraction is deliberately all it does: no
negotiation, no rewriting, and an absent marker falls back to
`default_version`. Handlers read it back with `get_version(request)`.
"""

import pytest
from starlette.requests import Request

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, get, get_version
from quadkit.web.routing.versioning import (
    VersioningConfig,
    VersioningMiddleware,
    VersioningStrategy,
)


class HelloController(Controller):
    @get("/hello")
    async def hello(self, request: Request) -> dict[str, str]:
        return {"version": get_version(request)}


class V7HelloController(Controller):
    @get("/v7/hello")
    async def hello_v7(self, request: Request) -> dict[str, str]:
        return {"version": get_version(request)}


def create_app(strategy: VersioningStrategy) -> Application:
    app = Application()
    app.add_module(
        WebModule.configure(
            controllers=[HelloController, V7HelloController],
            middleware=[VersioningMiddleware(VersioningConfig(strategy=strategy))],
        )
    )
    return app


@pytest.mark.asyncio
async def test_header_strategy_honors_header_and_default() -> None:
    async with WebTestBed(create_app(VersioningStrategy.HEADER)) as bed:
        pinned = bed.get("/hello", headers={"X-API-Version": "9"})
        assert pinned.json == {"version": "9"}

        unpinned = bed.get("/hello")
        assert unpinned.json == {"version": "1"}  # default_version fallback


@pytest.mark.asyncio
async def test_query_and_uri_strategies() -> None:
    async with WebTestBed(create_app(VersioningStrategy.QUERY)) as bed:
        assert bed.get("/hello", params={"api_version": "3"}).json == {"version": "3"}
        assert bed.get("/hello").json == {"version": "1"}

    async with WebTestBed(create_app(VersioningStrategy.URI)) as bed:
        assert bed.get("/v7/hello").json == {"version": "7"}
        assert bed.get("/hello").json == {"version": "1"}  # no v-segment present


@pytest.mark.asyncio
async def test_media_type_strategy_reads_the_accept_header() -> None:
    async with WebTestBed(create_app(VersioningStrategy.MEDIA_TYPE)) as bed:
        negotiated = bed.get(
            "/hello", headers={"Accept": "application/vnd.api.v2+json"}
        )
        assert negotiated.json == {"version": "2"}

        plain = bed.get("/hello", headers={"Accept": "application/json"})
        assert plain.json == {"version": "1"}
