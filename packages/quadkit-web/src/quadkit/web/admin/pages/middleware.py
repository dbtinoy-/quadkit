from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.logging import get_logger
from quadkit.web.middleware.base import MiddlewareRegistry
from quadkit.web.middleware.registry import MiddlewareAdapterRegistry

logger = get_logger(__name__)


class WebMiddlewarePage:
    """Middleware overview page for /admin/web/middleware."""

    def __init__(
        self,
        middleware_registry: MiddlewareRegistry | None = None,
        adapter_registry: MiddlewareAdapterRegistry | None = None,
    ) -> None:
        self._middleware_registry = middleware_registry
        self._adapter_registry = adapter_registry

    async def handle(self, request: Any) -> PageContent:
        if self._middleware_registry is None:
            return PageContent(
                title="Middleware",
                body=EmptyContent(
                    title="Middleware Registry Unavailable",
                    message="The middleware registry could not be resolved.",
                    icon="layers",
                ),
            )

        try:
            names = self._middleware_registry.get_middleware_order()
            stack = getattr(self._middleware_registry, "_middleware_stack", [])
        except Exception as exc:
            logger.warning("web_middleware.list_failed", error=str(exc))
            names = []
            stack = []

        if not names:
            return PageContent(
                title="Middleware",
                body=EmptyContent(
                    title="No Middleware Registered",
                    message="No middleware has been registered yet.",
                    icon="layers",
                ),
            )

        rows = tuple(
            (TableCell(name), TableCell(cls.__name__), TableCell(cls.__module__))
            for (_, cls, _), name in zip(stack, names, strict=True)
        )

        return PageContent(
            title="Middleware",
            body=TableContent(
                columns=("Name", "Class", "Module"),
                rows=rows,
            ),
        )
