"""Feature tour: role-based access control.

`@roles("admin", authorizer=auth)` hangs a RoleGuard on a handler. Guards run
before interceptors and before business code — a denied request never touches
the handler. The public seam is two protocols from `quadkit.contracts`:

* `AuthenticatorProtocol` — who are you? (stamps `request.state.user`)
* `AuthorizerProtocol` — are you allowed? (decides from roles/permissions)

Ship your own authenticator as plain ASGI middleware — two dozen lines stand
in for an identity provider here — and the framework enforces the rest.
"""

from dataclasses import dataclass

import pytest
from starlette.requests import Request
from starlette.types import Receive, Scope, Send

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, get, roles


@dataclass(frozen=True)
class RoleUser:
    """A tiny principal: a name plus the roles it holds."""

    name: str
    roles: frozenset[str]


class DemoAuthorizer:
    """`AuthorizerProtocol`: intersection of user roles with required roles."""

    async def authorize(self, user: RoleUser, action: str, resource: object) -> bool:
        return True  # decision surface kept for the protocol shape

    async def check_access(
        self,
        user: RoleUser,
        allowed_roles: set[str],
        resource: str | None = None,
    ) -> bool:
        return bool(user.roles & allowed_roles)


class StampUserMiddleware:
    """`AuthenticatorProtocol` stand-in: resolve the caller from a header.

    Production apps stamp the user from a JWT/session store here (the private
    quadkit-auth package ships that); the guard reads `request.state.user`
    the same way regardless.
    """

    def __init__(self, app) -> None:  # noqa: ANN001 — ASGI callable
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            raw = headers.get(b"x-user-roles")
            if raw is not None:
                user = RoleUser(
                    name=headers.get(b"x-user-name", b"anon").decode(),
                    roles=frozenset(
                        r.strip() for r in raw.decode().split(",") if r.strip()
                    ),
                )
                scope.setdefault("state", {})["user"] = user
        await self.app(scope, receive, send)


AUTHORIZER = DemoAuthorizer()


class TeamController(Controller):
    prefix = "/team"

    @get("/dashboard")
    async def dashboard(self) -> dict:
        return {"visibility": "public"}

    @get("/admin")
    @roles("admin", authorizer=AUTHORIZER)
    async def admin_only(self, request: Request) -> dict:
        return {"visibility": "admin"}

    @get("/reports")
    @roles("viewer", "admin", authorizer=AUTHORIZER)
    async def reports(self, request: Request) -> dict:
        return {"visibility": "viewer-or-admin"}


def create_app() -> Application:
    app = Application()
    app.add_module(
        WebModule.configure(
            controllers=[TeamController],
            middleware=[StampUserMiddleware],
        )
    )
    return app


@pytest.mark.asyncio
async def test_roles_guard_enforcement():
    async with WebTestBed(create_app()) as bed:
        # Public route: reachable without a principal.
        assert bed.get("/team/dashboard").status_code == 200

        # No principal → denied.
        denied = bed.get("/team/admin")
        assert denied.status_code == 403

        # Principal, wrong role → denied.
        ops = bed.get("/team/admin", headers={"x-user-roles": "ops"})
        assert ops.status_code == 403

        # Principal, required role → admitted.
        admin = bed.get(
            "/team/admin",
            headers={"x-user-roles": "ops,admin", "x-user-name": "ada"},
        )
        assert admin.status_code == 200
        assert admin.json == {"visibility": "admin"}

        # Either-of roles: viewer qualifies for /reports.
        viewer = bed.get("/team/reports", headers={"x-user-roles": "viewer"})
        assert viewer.status_code == 200
