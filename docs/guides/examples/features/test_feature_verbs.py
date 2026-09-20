"""Feature tour: the quiet verbs — HEAD, OPTIONS, PATCH.

Beyond the CRUD staples, the router speaks the metadata verbs with the
same one-decorator ergonomics. HEAD needs no handler of its own on a
GET path — every `@get` route answers HEAD automatically, headers and
no body, exactly by HTTP semantics. (Mind the edge: on a shared path the
GET route always wins for HEAD, because routes are matched in method
order — declare `@head` for HEAD-only endpoints that must never serve
the body.) `@options` advertises what a resource allows; `@patch` takes
the partial update and merges it.
"""

import pytest
from starlette.requests import Request

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, Response, WebModule, get, head, options, patch
from quadkit.web.config.top_level import SecurityConfig, WebConfig

STORE: dict[str, object] = {"title": "wave notes", "body": "v1", "version": 1}


class DocsController(Controller):
    @get("/docs/spec")
    async def fetch(self) -> dict[str, object]:
        return dict(STORE)

    @head("/docs/spec/heartbeat")
    async def heartbeat(self) -> Response:
        # HEAD-only by design: cheap liveness + version check, no body ever.
        return Response(
            status_code=200,
            headers={"X-Doc-Version": str(STORE["version"])},
        )

    @options("/docs/spec")
    async def meta(self) -> Response:
        return Response(
            status_code=204,
            headers={"Allow": "GET, HEAD, OPTIONS, PATCH"},
        )

    @patch("/docs/spec")
    async def amend(self, request: Request) -> dict[str, object]:
        changes = await request.json()
        STORE.update(changes)
        STORE["version"] = int(str(STORE["version"])) + 1
        return dict(STORE)


def create_app() -> Application:
    app = Application()
    app.add_module(
        WebModule.configure(
            controllers=[DocsController],
            web_config=WebConfig(security=SecurityConfig(enable_csrf=False)),
        )
    )
    return app


@pytest.mark.asyncio
async def test_head_comes_free_with_get_and_explicit_head_stays_bodiless() -> None:
    async with WebTestBed(create_app()) as bed:
        # Every GET route answers HEAD on its own — headers, no body.
        free = bed.client.head("/docs/spec")
        assert free.status_code == 200
        assert free.text == ""
        assert free.headers["content-type"].startswith("application/json")

        # The explicit HEAD-only route stamps its custom header …
        before = bed.client.head("/docs/spec/heartbeat")
        assert before.status_code == 200
        assert before.text == ""
        assert before.headers["x-doc-version"] == "1"

        # … and stays HEAD-only: a GET there is 405, not a body leak.
        assert bed.get("/docs/spec/heartbeat").status_code == 405

        amended = bed.patch("/docs/spec", json={"title": "wave notes, v2"})
        assert amended.json["title"] == "wave notes, v2"
        assert amended.json["version"] == 2  # server-managed field bumped

        after = bed.client.head("/docs/spec/heartbeat")
        assert after.headers["x-doc-version"] == "2"
        assert bed.get("/docs/spec").json["body"] == "v1"  # patch merged, not replaced


@pytest.mark.asyncio
async def test_options_advertises_the_allowed_verbs() -> None:
    async with WebTestBed(create_app()) as bed:
        response = bed.client.options("/docs/spec")
        assert response.status_code == 204
        assert response.headers["allow"] == "GET, HEAD, OPTIONS, PATCH"
