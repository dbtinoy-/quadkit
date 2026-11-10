"""Inbox request handlers for the notification admin contributor.

Backs the topbar notification bell with persisted JSON endpoints:
list + unread count, mark-read, and mark-all-read. The service is
resolved lazily from the request container when available, falling
back to the default (in-memory) InboxService otherwise.
"""

from __future__ import annotations

from typing import Any

from starlette.responses import JSONResponse

from quadkit.logging import get_logger
from quadkit.notification.inbox.service import InboxService

logger = get_logger(__name__)


def _user_id(request: Any) -> Any | None:
    """Extract the current user ID from a request.

    Real ASGI requests carry the user in ``scope["user"]`` (populated by
    the admin auth middleware, mirrored into ``scope["state"]["user"]``).
    Minimal hosts that pass plain request stand-ins expose ``.user`` as a
    plain attribute instead — read both, never the raising
    ``request.user`` property.

    Args:
        request: The ASGI request.

    Returns:
        The user ID, or ``None`` when unauthenticated.
    """
    scope = getattr(request, "scope", None)
    if isinstance(scope, dict):
        user = scope.get("user")
        if user is None:
            state = scope.get("state")
            user = state.get("user") if isinstance(state, dict) else None
        if isinstance(user, dict):
            return user.get("id")
        return getattr(user, "id", None) if user is not None else None

    user = getattr(request, "user", None)
    return getattr(user, "id", None) if user is not None else None


def _message_to_dict(message: Any) -> dict[str, Any]:
    """Serialize an InboxMessage for the JSON API.

    Args:
        message: An ``InboxMessage`` instance.

    Returns:
        JSON-safe message dict.
    """
    return {
        "id": message.id,
        "title": message.title,
        "message": message.body,
        "read": message.read,
        "timestamp": message.created_at.isoformat(),
    }


class InboxHandlers:
    """JSON endpoint handlers for the persisted notification inbox.

    Args:
        service: Inbox service. When ``None``, the service is resolved
            lazily per-request from the request container, falling back
            to the default in-memory service.
    """

    def __init__(self, service: InboxService | None = None) -> None:
        self._service = service

    async def _resolve_service(self, request: Any) -> InboxService:
        """Resolve an InboxService for the request.

        Priority: constructor-injected service > request container >
        default in-memory service.

        Args:
            request: The ASGI request.

        Returns:
            An InboxService instance.
        """
        if self._service is not None:
            return self._service
        container = getattr(getattr(request, "state", None), "container", None)
        if container is None:
            app_state = getattr(getattr(request, "app", None), "state", None)
            container = getattr(app_state, "container", None)
        if container is not None:
            try:
                service: InboxService = await container.resolve(InboxService)
                return service
            except Exception as exc:  # noqa: BLE001 — non-fatal
                logger.warning("inbox_handlers.resolve_failed", error=str(exc))
        return InboxService()

    async def get_inbox(self, request: Any) -> JSONResponse:
        """Return the current user's inbox as JSON.

        Args:
            request: The ASGI request.

        Returns:
            JSON with ``unread_count`` and ``notifications``.
        """
        user_id = _user_id(request)
        if user_id is None:
            return JSONResponse({"unread_count": 0, "notifications": []})

        service = await self._resolve_service(request)
        limit = 10
        try:
            limit = max(1, min(int(request.query_params.get("limit", 10)), 50))
        except (TypeError, ValueError):
            limit = 10

        messages = await service.get_inbox(user_id, unread_only=False)
        unread = await service.count_unread(user_id)

        return JSONResponse(
            {
                "unread_count": unread,
                "notifications": [_message_to_dict(m) for m in messages[:limit]],
            },
        )

    async def mark_read(self, request: Any) -> JSONResponse:
        """Mark a single message as read for the current user.

        Args:
            request: The ASGI request.

        Returns:
            JSON acknowledgement.
        """
        user_id = _user_id(request)
        if user_id is None:
            return JSONResponse({"ok": False}, status_code=401)

        message_id = request.path_params.get("message_id", "")
        service = await self._resolve_service(request)
        await service.mark_read(message_id, user_id)
        return JSONResponse({"ok": True})

    async def mark_all_read(self, request: Any) -> JSONResponse:
        """Mark all of the current user's messages as read.

        Args:
            request: The ASGI request.

        Returns:
            JSON acknowledgement.
        """
        user_id = _user_id(request)
        if user_id is None:
            return JSONResponse({"ok": False}, status_code=401)

        service = await self._resolve_service(request)
        await service.mark_all_read(user_id)
        return JSONResponse({"ok": True})

    async def health(self) -> str:
        """Probe the underlying inbox store health.

        Returns:
            Human-readable health status message.
        """
        if self._service is None:
            return "inbox service not initialized"
        result = await self._service._store.health_check()  # noqa: SLF001
        return f"{result.status.value}: {result.message}"


__all__ = ["InboxHandlers"]
