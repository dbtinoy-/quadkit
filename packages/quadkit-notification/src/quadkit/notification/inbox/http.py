"""Explicit ASGI adapter for recipient-scoped inbox operations.

The host must supply a resolver that verifies the request's authentication and
returns its subject. The adapter does not perform authentication itself and
must not be mounted with a resolver reading user-supplied IDs or headers.
Sending remains a trusted server-side ``InboxService`` operation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
import re
from typing import TYPE_CHECKING, Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

if TYPE_CHECKING:
    from quadkit.contracts.notification.inbox import InboxMessage
    from quadkit.notification.inbox.service import InboxService


# The host must authenticate before returning a subject. There is deliberately
# no permissive default resolver and no parameter containing a recipient ID.
SubjectResolver = Callable[[Request], Awaitable[str | None]]


def _message(message: InboxMessage) -> dict[str, Any]:
    """Return the recipient-facing, deliberately narrow response shape."""
    return {
        "id": message.id,
        "title": message.title,
        "body": message.body,
        "read": message.read,
        "created_at": message.created_at.isoformat(),
    }


class InboxHttpAdapter:
    """Build inbox routes around a shared service and trusted auth resolver.

    The resolver must establish an authenticated principal using the host's
    auth stack, not request input. A missing/empty subject is rejected with
    401. A missing or cross-user message is returned as 404 for reads. Writes
    use owner-scoped store predicates and return the same 204 for missing,
    cross-user and existing IDs, so they do not reveal existence.

    Mount these routes only in a host that also applies its CSRF and other
    deployment-specific protections. No arbitrary-recipient send route exists.
    """

    def __init__(self, service: InboxService, resolve_subject: SubjectResolver) -> None:
        self._service = service
        self._resolve_subject = resolve_subject

    async def _subject(self, request: Request) -> str | None:
        subject = await self._resolve_subject(request)
        if not isinstance(subject, str) or not subject.strip():
            return None
        return subject

    async def list(self, request: Request) -> Response:
        """List only the authenticated subject's messages."""
        subject = await self._subject(request)
        if subject is None:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        try:
            limit = int(request.query_params.get("limit", "20"))
            offset = int(request.query_params.get("offset", "0"))
        except ValueError:
            return JSONResponse({"detail": "Invalid pagination"}, status_code=400)
        # SQLite and PostgreSQL bind offsets as signed 64-bit integers. Reject
        # larger values at the HTTP boundary instead of raising a driver error.
        if not 1 <= limit <= 100 or not 0 <= offset <= 2**63 - 1:
            return JSONResponse({"detail": "Invalid pagination"}, status_code=400)
        messages = await self._service.get_inbox(subject, limit=limit, offset=offset)
        return JSONResponse({"items": [_message(message) for message in messages]})

    async def get(self, request: Request) -> Response:
        """Retrieve one message, concealing other recipients' IDs."""
        subject = await self._subject(request)
        if subject is None:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        message = await self._service.get_message_for_user(
            request.path_params["message_id"], subject
        )
        if message is None:
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return JSONResponse(_message(message))

    async def mark_read(self, request: Request) -> Response:
        """Mark the subject's message read without revealing existence."""
        subject = await self._subject(request)
        if subject is None:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        await self._service.mark_read(request.path_params["message_id"], subject)
        return Response(status_code=204)

    async def delete(self, request: Request) -> Response:
        """Delete the subject's message without revealing existence."""
        subject = await self._subject(request)
        if subject is None:
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        await self._service.delete(request.path_params["message_id"], subject)
        return Response(status_code=204)

    def routes(self, prefix: str = "/inbox") -> Sequence[Route]:
        """Create Starlette routes; the host owns mounting and middleware."""
        if (
            not isinstance(prefix, str)
            or re.fullmatch(r"/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*", prefix) is None
        ):
            raise ValueError("inbox prefix must contain literal path segments")
        return [
            Route(prefix, self.list, methods=["GET"]),
            Route(f"{prefix}/{{message_id}}", self.get, methods=["GET"]),
            Route(f"{prefix}/{{message_id}}/read", self.mark_read, methods=["POST"]),
            Route(f"{prefix}/{{message_id}}", self.delete, methods=["DELETE"]),
        ]
