"""Value types for HTTP service mesh contracts."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["ServiceInfo"]


@dataclass(frozen=True)
class ServiceInfo:
    """Information about a registered service instance."""

    name: str
    host: str
    port: int
    metadata: dict[str, str] | None = None
