"""Pure ASGI middleware for canonical web hook emission."""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Any, cast

from quadkit.contracts.core import HookRegistryProtocol
from quadkit.web.hooks import WebRequestReceivedHook, WebResponsePreparedHook

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Receive, Scope, Send


class WebHooksMiddleware:
    """Emit request/response lifecycle hooks around HTTP ASGI traffic."""

    def __init__(
        self,
        app: ASGIApp,
        hooks: HookRegistryProtocol | None = None,
    ) -> None:
        self.app = app
        self._hooks = hooks

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Emit canonical hooks for HTTP requests and prepared responses."""
        if scope["type"] != "http" or self._hooks is None:
            # Unconfigured hook emission must not cost anything: pass the
            # request through untouched — no send-wrapper closure, no hook
            # payload objects.
            await self.app(scope, receive, send)
            return

        path = cast("str", scope.get("path", ""))
        method = cast("str", scope.get("method", ""))
        await self._emit_action(
            "request.received",
            WebRequestReceivedHook(path=path, method=method),
        )

        response_started = False

        async def send_with_hooks(message: MutableMapping[str, Any]) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start" and not response_started:
                response_started = True
                await self._emit_action(
                    "response.prepared",
                    WebResponsePreparedHook(
                        path=path,
                        status_code=cast("int", message.get("status", 200)),
                    ),
                )
            await send(message)

        await self.app(scope, receive, send_with_hooks)

    async def _emit_action(self, hook_name: str, payload: object) -> None:
        """Emit a hook action when a registry is available."""
        if self._hooks is None:
            return

        await self._hooks.call_action(hook_name, payload=payload)


__all__ = ["WebHooksMiddleware"]
