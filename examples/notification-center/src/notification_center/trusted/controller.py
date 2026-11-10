"""Authenticated HTTP adapter; no send, recipient-selection or worker endpoint."""

from __future__ import annotations

from collections.abc import Callable
import json  # noqa: TID251 -- native fast JSON ignores duplicate-key hooks; refuse ambiguous input.
from typing import TypeVar
from uuid import UUID

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from notification_center.trusted.service import (
    PublicationRefusedError,
    TrustedPublication,
)
from quadkit.contracts.web.security_metadata import (
    HTTP_BEARER_DOCUMENTATION_ATTRIBUTE,
    HttpBearerDocumentation,
)
from quadkit.notification.inbox.http import InboxHttpAdapter
from quadkit.web import Controller, delete, get, post

_Handler = TypeVar("_Handler", bound=Callable[..., object])


def _bearer(handler: _Handler) -> _Handler:
    """Declare the enforced native bearer contract; no auth or handler wrapping."""
    setattr(handler, HTTP_BEARER_DOCUMENTATION_ATTRIBUTE, HttpBearerDocumentation())
    return handler


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


async def _body(request: Request) -> dict[str, object]:
    """Reject ambiguous/oversized input even without upstream middleware."""
    content_types = request.headers.getlist("content-type")
    if (
        len(content_types) != 1
        or content_types[0].split(";", 1)[0].strip().lower() != "application/json"
    ):
        raise PublicationRefusedError(415, "application/json required")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 4096:
            raise PublicationRefusedError(413, "Request body too large")
        raw.extend(chunk)
    try:
        data = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError) as exc:
        raise PublicationRefusedError(400, "Invalid JSON object") from exc
    if not isinstance(data, dict):
        raise PublicationRefusedError(400, "JSON object required")
    return data


class TrustedPublicationController(Controller):
    """Native controller for one explicitly composed local application."""

    def __init__(self, service: TrustedPublication) -> None:
        self.service = service
        self.inbox = InboxHttpAdapter(service.inbox, service.subject)

    @post("/posts")
    @_bearer
    async def create(self, request: Request) -> Response:
        """Create an authorized draft with a deliberately narrow input contract."""
        try:
            await self.service.publisher(request)
            data = await _body(request)
            title = data.get("title")
            if (
                set(data) != {"title"}
                or not isinstance(title, str)
                or not title.strip()
                or len(title) > 120
            ):
                raise PublicationRefusedError(
                    422, "Only a title of 1-120 characters is accepted"
                )
            return JSONResponse(await self.service.create(title), status_code=201)
        except PublicationRefusedError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @post("/posts/{post_id}/publish")
    @_bearer
    async def publish(self, post_id: str, request: Request) -> Response:
        """Queue on commit; a 202 never claims inbox delivery has already happened."""
        try:
            await self.service.publisher(request)
            if await _body(request):
                raise PublicationRefusedError(422, "Publish accepts no input fields")
            try:
                UUID(post_id)
            except ValueError as exc:
                raise PublicationRefusedError(422, "Invalid post ID") from exc
            return JSONResponse(await self.service.publish(post_id), status_code=202)
        except PublicationRefusedError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @get("/posts/search")
    @_bearer
    async def search(self, request: Request) -> Response:
        """Search is permission-protected and includes drafts, not a public feed."""
        try:
            await self.service.publisher(request)
            query = request.query_params.get("q", "")
            if not query.strip() or len(query) > 120 or "\x00" in query:
                raise PublicationRefusedError(
                    422, "Query must contain 1-120 non-NUL characters"
                )
            return JSONResponse({"items": await self.service.search(query)})
        except PublicationRefusedError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=exc.status)

    @get("/inbox")
    @_bearer
    async def inbox_list(self, request: Request) -> Response:
        """Delegate all owner filtering to the native authenticated adapter."""
        return await self.inbox.list(request)

    @get("/inbox/{message_id}")
    @_bearer
    async def inbox_get(self, request: Request) -> Response:
        """Never expose another recipient's message by ID."""
        return await self.inbox.get(request)

    @post("/inbox/{message_id}/read")
    @_bearer
    async def inbox_read(self, request: Request) -> Response:
        """Owner-scoped mutation; identical 204 for missing/foreign IDs."""
        return await self.inbox.mark_read(request)

    @delete("/inbox/{message_id}")
    @_bearer
    async def inbox_delete(self, request: Request) -> Response:
        """Deletion does not erase the native idempotency receipt."""
        return await self.inbox.delete(request)
