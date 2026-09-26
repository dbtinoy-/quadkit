"""Convention followed: **Controller pattern** — stateless HTTP adapters; services return ``Result[T, E]``; failures map to RFC-9457 ``ProblemDetail``.

JSON API for the RBAC console — the **Result-pattern showcase**.

Every handler returns ``Result<Ok, Err>`` instead of raising or returning
raw responses.  The web pipeline then does the boring work:

- ``Ok(payload)``            → serialized as JSON (or rendered)
- ``Err(ValidationError)``   → HTTP 422 ProblemDetail
- ``Err(AuthenticationError)`` → HTTP 401
- ``Err(PermissionDeniedError)`` → HTTP 403
- ``Err(NotFoundError)``     → HTTP 404

So handlers read like use-cases ("authenticate → authorize → act") and
error-to-HTTP mapping lives in exactly one place.  Compare with the
try/except-and-JSONResponse dance in traditional stacks.

Auth flow across these endpoints: login binds a session cookie via
``SessionCookieBackend``; every protected endpoint then authenticates
through :meth:`_authenticated_user` and authorizes through
``AuthorizationService`` before touching the article store.
"""

from __future__ import annotations

from typing import Any

from rbac_console.domain.articles import ArticleStore
from rbac_console.domain.personas import PERSONAS, PersonaDirectory
from starlette.requests import Request

from quadkit.auth import SessionCookieBackend, UserService
from quadkit.auth.authz import AuthorizationService
from quadkit.contracts.exceptions import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from quadkit.result import Err, Ok, Result
from quadkit.serialization import loads as json_loads
from quadkit.web import Controller, JSONResponse, get, post

PERSONA_PASSWORD = "Demo-Password-1"
# (action, resource) pairs the matrix renders; required permission is
# f"{resource}.{action}" per AuthorizationService's pattern grammar.
MATRIX_CHECKS: tuple[tuple[str, str], ...] = (
    ("view", "articles"),
    ("create", "articles"),
    ("update", "articles"),
    ("delete", "articles"),
    ("open", "admin_console"),
)


def _granted(verdict: Result[bool, Any]) -> bool:
    """Collapse an authorize() verdict to a plain boolean.

    ``AuthorizationService.authorize`` returns ``Result[bool, ...]``:
    ``Ok(True)`` granted, ``Ok(False)`` denied by policy, ``Err`` denied by
    failure.  All three collapse to "may proceed or not".
    """
    return bool(verdict.unwrap()) if verdict.is_ok() else False


class RbacApiController(Controller):
    """RBAC API consumed by the UI's vanilla-JS client.

    Quadkit pattern: controllers are stateless handlers that receive
    collaborators via constructor injection.  The framework resolves the
    controller when a request matches its routes — you never instantiate
    it manually.

    Route decorators (@get, @post) come from quadkit.web, not Starlette
    directly — they integrate with the framework's middleware stack.
    """

    def __init__(
        self,
        users: UserService,
        authz: AuthorizationService,
        cookies: SessionCookieBackend,
        personas: PersonaDirectory,
        articles: ArticleStore,
    ) -> None:
        self._users = users
        self._authz = authz
        self._cookies = cookies
        self._personas = personas
        self._articles = articles

    @post("/api/login")
    async def login(
        self, request: Request
    ) -> Result[JSONResponse, ValidationError | NotFoundError]:
        """Log in as one of the seeded personas.

        Return type uses ``Result[T, E]`` — the web pipeline maps Err
        types to HTTP status codes automatically (ValidationError → 422,
        NotFoundError → 404, AuthenticationError → 401, PermissionDeniedError → 403).
        """
        data = json_loads(await request.body())
        persona = str(data.get("persona", ""))
        if persona not in PERSONAS:
            return Err(ValidationError(f"unknown persona {persona!r}"))

        user = self._personas.get(persona)
        if user is None:
            return Err(NotFoundError(f"unknown persona {persona!r}"))
        response = JSONResponse(
            {"ok": True, "persona": persona, "roles": list(user.roles)}
        )
        await self._cookies.login(response, user.user_id)
        return Ok(response)

    @post("/api/logout")
    async def logout(self, request: Request) -> JSONResponse:
        response = JSONResponse({"ok": True})
        await self._cookies.logout(request, response)
        return response

    async def _authenticated_user(
        self, request: Request
    ) -> Result[Any, AuthenticationError]:
        """Authenticate via session cookie — shared guard for protected endpoints.

        This helper is called at the top of each protected handler.
        If it returns Err(AuthenticationError), the pipeline maps it to 401.
        """
        user = await self._cookies.authenticate(request)
        if user is None:
            return Err(AuthenticationError("not authenticated"))
        return Ok(user)

    def _effective(self, user: Any) -> set[str]:
        """Explicit user permissions ∪ role-derived patterns (inherited)."""
        effective: set[str] = set()
        if getattr(user, "permissions", None):
            effective.update(user.permissions)
        for role in getattr(user, "roles", []) or []:
            effective |= self._authz.get_role_permissions(role)
        return effective

    @get("/api/me")
    async def me(
        self,
        request: Request,
    ) -> Result[dict, AuthenticationError]:
        user_result = await self._authenticated_user(request)
        if user_result.is_err():
            return Err(user_result.unwrap_err())
        user = user_result.unwrap()
        return Ok(
            {
                "email": user.email,
                "roles": list(user.roles),
                "permissions": sorted(self._effective(user)),
            }
        )

    @get("/api/matrix")
    async def matrix(self, request: Request) -> JSONResponse:
        """The permission grid computed live via authorize() per persona."""
        cells: dict[str, dict[str, bool]] = {}
        for role in PERSONAS:
            user = self._personas.get(role)
            row = {}
            for action, resource in MATRIX_CHECKS:
                verdict = await self._authz.authorize(user, action, resource)
                row[f"{resource}.{action}"] = _granted(verdict)
            cells[role] = row

        return JSONResponse(
            {
                "personas": self._personas.roles(),
                "checks": [
                    f"{resource}.{action}" for action, resource in MATRIX_CHECKS
                ],
                "cells": cells,
            }
        )

    @post("/api/try")
    async def try_check(self, request: Request) -> Result[dict, ValidationError]:
        """Run one authorize() verdict for a persona/action/resource triple."""
        data = json_loads(await request.body())
        role = str(data.get("role", ""))
        action = str(data.get("action", ""))
        resource = str(data.get("resource", ""))
        if role not in PERSONAS:
            return Err(ValidationError(f"unknown persona {role!r}"))

        user = self._personas.get(role)
        verdict = await self._authz.authorize(user, action, resource)
        granted = _granted(verdict)
        return Ok(
            {
                "granted": granted,
                "required": f"{resource}.{action}",
                "verdict": "Ok(True)" if granted else "Ok(False)",
            }
        )

    @get("/api/articles")
    async def list_articles(
        self,
        request: Request,
    ) -> Result[dict, AuthenticationError]:
        user_result = await self._authenticated_user(request)
        if user_result.is_err():
            return Err(user_result.unwrap_err())
        return Ok(
            {
                "articles": [
                    {"id": a.id, "title": a.title, "body": a.body}
                    for a in self._articles.list()
                ]
            }
        )

    @post("/api/articles", status_code=201)
    async def create_article(
        self,
        request: Request,
    ) -> Result[dict, AuthenticationError | PermissionDeniedError]:
        """Create an article — the deny-before-mutate guard rejects this for viewers.

        Pattern: authenticate → authorize → act.  If either check fails,
        return an Err and let the pipeline map it to the correct HTTP status.
        This is the standard Quadkit guard pattern.
        """
        user_result = await self._authenticated_user(request)
        if user_result.is_err():
            return Err(user_result.unwrap_err())
        user = user_result.unwrap()
        allowed = await self._authz.authorize(user, "create", "articles")
        if not _granted(allowed):
            return Err(PermissionDeniedError("missing articles.create"))
        data = json_loads(await request.body())
        article = self._articles.create(
            title=str(data.get("title", "untitled")),
            body=str(data.get("body", "")),
        )
        return Ok({"ok": True, "article": {"id": article.id}})


__all__ = ["RbacApiController"]
