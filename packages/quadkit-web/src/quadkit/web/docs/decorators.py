"""OpenAPI decorators for quadkit-web."""
from __future__ import annotations

from typing import Any

from quadkit.web.routing.types import RoutableProtocol


def openapi(
    summary: str | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
    operation_id: str | None = None,
    responses: dict[int | str, Any] | None = None,
    deprecated: bool = False,
    **kwargs: Any,
) -> Any:
    """Decorator to add OpenAPI metadata to an endpoint."""

    def decorator(func: RoutableProtocol) -> RoutableProtocol:
        # Initialise route config dict if it doesn't exist yet
        if not hasattr(func, "_route_config") or func._route_config is None:
            func._route_config = {}

        # Merge new metadata; _route_config is guaranteed to be a dict here
        route_config: dict[str, Any] = func._route_config
        route_config.update(
            {
                "summary": summary,
                "description": description,
                "tags": tags,
                "operation_id": operation_id,
                "responses": responses,
                "deprecated": deprecated,
                **kwargs,
            },
        )
        return func

    return decorator
