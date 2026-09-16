"""DI Scope types for Quadkit Framework."""

from __future__ import annotations

from enum import StrEnum


class ServiceScope(StrEnum):
    """Dependency injection scopes."""

    SINGLETON = "singleton"
    SCOPED = "scoped"
    TRANSIENT = "transient"


__all__ = ["ServiceScope"]
