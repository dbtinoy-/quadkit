from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RoutableProtocol(Protocol):
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...

    # Optional attributes added by decorators
    _route_config: dict[str, Any] | None
    _param_metadata: list[dict[str, Any]] | None
    _dependencies: list[dict[str, Any]] | None
