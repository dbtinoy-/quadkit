"""Feature tour: identity is request state, extracted by one-liners.

Quadkit doesn't prescribe an auth stack — it prescribes a seam: whatever
proves identity (token middleware, SSO gateway, session cookie) writes
`request.state.user`, and handlers read it back through two dependency
functions. `get_current_user_optional` returns `None` for guests;
`get_current_user_required` answers 401 with a `WWW-Authenticate:
Bearer` challenge. The middleware below trusts the harness's `X-User-ID`
header verbatim — swap its body for real verification in production
(see `examples/auth-tokens`). `get_request_id` reads the same state
trough for the request ID the context middleware stamps.
"""

import pytest
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import (
    Controller,
    WebModule,
    get,
    get_current_user_optional,
    get_current_user_required,
    get_request_id,
)


class HeaderUserMiddleware:
    """App-provided identity seam: prove, then write `request.state.user`."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            user_id = headers.get("x-user-id")
            if user_id is not None:
                scope.setdefault("state", {})["user"] = {"id": user_id}
        await self._app(scope, receive, send)


class MeController(Controller):
    @get("/me")
    async def me(self, request: Request) -> dict[str, str]:
        user = await get_current_user_required(request)
        return {"id": str(user["id"])}

    @get("/welcome")
    async def welcome(self, request: Request) -> dict[str, str]:
        user = await get_current_user_optional(request)
        return {"message": f"hello {user['id']}" if user else "hello guest"}

    @get("/trace")
    async def trace(self, request: Request) -> dict[str, str]:
        return {"request_id": await get_request_id(request)}


def create_app() -> Application:
    app = Application()
    app.add_module(
        WebModule.configure(
            controllers=[MeController],
            middleware=[HeaderUserMiddleware],
        )
    )
    return app


@pytest.mark.asyncio
async def test_required_user_answers_401_with_a_challenge() -> None:
    async with WebTestBed(create_app()) as bed:
        anonymous = bed.get("/me")
        assert anonymous.status_code == 401
        headers = {k.lower(): v for k, v in anonymous.headers.items()}
        assert headers["www-authenticate"] == "Bearer"

        bed.client.as_user("u-7")  # harness sends X-User-ID from here on
        authed = bed.get("/me")
        assert authed.status_code == 200
        assert authed.json == {"id": "u-7"}


@pytest.mark.asyncio
async def test_optional_user_distinguishes_guest_from_member() -> None:
    async with WebTestBed(create_app()) as bed:
        assert bed.get("/welcome").json == {"message": "hello guest"}

        bed.client.as_user("u-7")
        assert bed.get("/welcome").json == {"message": "hello u-7"}


@pytest.mark.asyncio
async def test_request_id_round_trips_through_state() -> None:
    async with WebTestBed(create_app()) as bed:
        # The context middleware honors an incoming X-Request-ID …
        traced = bed.get("/trace", headers={"X-Request-ID": "req-abc"})
        assert traced.json == {"request_id": "req-abc"}

        # … and stamps one when the client doesn't supply it.
        generated = bed.get("/trace")
        rid = generated.json["request_id"]
        assert isinstance(rid, str) and rid
