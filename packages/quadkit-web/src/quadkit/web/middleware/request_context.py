"""Request context middleware for Quadkit Framework.

Consolidates request ID generation, context variable population,
tracing propagation, and structlog binding into a single middleware.

If ``RequestIDMiddleware`` has already set a request ID in the scope,
this middleware reuses it. Otherwise it generates or extracts one from
the configured request ID header.
"""

from __future__ import annotations

from typing import Any
import uuid

from starlette.types import ASGIApp, Receive, Scope, Send

from quadkit.contracts.core.identity import IdGeneratorProtocol
from quadkit.primitives.context import (
    Context,
    ContextVarRegistry,
    RequestContext,
    create_default_context,
)
from quadkit.web.middleware._headers import get_header, sanitize_request_id
from quadkit.web.middleware.tracing import load_trace_to_context


class RequestContextMiddleware:
    """ASGI middleware that populates global request context."""

    def __init__(
        self,
        app: ASGIApp,
        context: Context | None = None,
        registry: ContextVarRegistry | None = None,
        header_name: str = "X-Request-ID",
        tenant_header_name: str = "X-Tenant-ID",
        ids: IdGeneratorProtocol | None = None,
    ) -> None:
        self.app = app
        self._context = context or create_default_context()
        self._registry = registry or self._context.registry
        self.header_name = header_name.lower().encode()
        self.tenant_header_name = tenant_header_name.lower().encode()
        self._ids = ids

    def _resolve_tenant_id(self, scope: Scope) -> str | None:
        state = scope.get("state", {})
        tenant_id = state.get("tenant_id")
        if tenant_id is not None:
            return str(tenant_id)

        tenant_header = get_header(scope, self.tenant_header_name)
        return tenant_header.decode() if tenant_header else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state = scope.setdefault("state", {})

        request_id = state.get("request_id")
        if not request_id:
            inbound = get_header(scope, self.header_name)
            # H-01: inbound ids are client-controlled — accept only short
            # URL-safe tokens; anything else (CRLF, control chars, oversized,
            # non-ascii) is dropped and a fresh id generated below. The
            # rejected value is never echoed.
            request_id = sanitize_request_id(
                inbound.decode("ascii", "replace") if inbound is not None else None
            )
        if not request_id:
            request_id = f"req_{self._ids.generate() if self._ids else uuid.uuid4().hex[:12]}"

        method = scope.get("method")
        path = scope.get("path")
        user_id = state.get("user_id")
        tenant_id = self._resolve_tenant_id(scope)

        ctx = RequestContext(
            self._registry,
            request_id=request_id,
            method=method,
            path=path,
            user_id=str(user_id) if user_id is not None else None,
            tenant_id=tenant_id,
        )

        traceparent = get_header(scope, b"traceparent")
        if traceparent:
            load_trace_to_context(ctx, traceparent.decode())

        async def send_wrapper(message: Any) -> None:
            if message["type"] == "http.response.start":
                msg_headers = list(message.get("headers", []))
                msg_headers.append((self.header_name, request_id.encode()))
                message["headers"] = msg_headers
            await send(message)

        with ctx as active_request_context:
            state["request_id"] = request_id
            state["request_context"] = active_request_context
            await self.app(scope, receive, send_wrapper)
