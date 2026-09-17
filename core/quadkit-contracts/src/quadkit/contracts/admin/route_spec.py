from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


@dataclass(frozen=True, kw_only=True)
class AdminRouteSpec:
    """Contributor-supplied route, registered automatically by admin's router."""

    path: str
    method: HttpMethod = "GET"
    handler: Any
    name: str
    permissions: frozenset[str] = field(default_factory=frozenset)


__all__ = ["AdminRouteSpec"]
