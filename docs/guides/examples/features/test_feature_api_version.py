"""Feature tour: API versioning.

`@api_version(1)` mounts a controller under `/v1/...`; a v2 controller
answers the same logical route under `/v2/...`; marking v1
`deprecated=True` injects `Deprecation`/`Sunset` response headers for
every v1 handler. One decorator — routing, deprecation, and headers.
"""

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, api_version, get


@api_version(1, deprecated=True, sunset="2030-01-01")
class UserControllerV1(Controller):
    prefix = "/users"

    @get("")
    async def list_users(self) -> dict:
        return {"version": 1, "users": ["ada"]}


@api_version(2)
class UserControllerV2(Controller):
    prefix = "/users"

    @get("")
    async def list_users(self) -> dict:
        return {"version": 2, "users": ["ada", "grace"]}


def create_app() -> Application:
    app = Application()
    app.add_module(
        WebModule.configure(controllers=[UserControllerV1, UserControllerV2])
    )
    return app


@pytest.mark.asyncio
async def test_versions_are_mounted_side_by_side():
    async with WebTestBed(create_app()) as bed:
        v1 = bed.get("/v1/users")
        assert v1.status_code == 200
        assert v1.json == {"version": 1, "users": ["ada"]}

        v2 = bed.get("/v2/users")
        assert v2.status_code == 200
        assert v2.json == {"version": 2, "users": ["ada", "grace"]}

        # Deprecation contract: headers on v1 only.
        assert v1.headers.get("deprecation") == "true"
        assert v1.headers.get("sunset") == "2030-01-01"
        assert "deprecation" not in v2.headers
