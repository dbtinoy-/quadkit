"""Typed context keys for the Quadkit Framework.

Pure-data :class:`ContextKey` instances and the well-known request/trace
key constants consumed by :mod:`quadkit.primitives.context`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class ContextKey(Generic[T]):
    """Immutable, typed key for context-variable access (pure data)."""

    name: str
    default: T | None = None


# ---------------------------------------------------------------------------
# Well-known Context Keys  (pure data constants — no side-effects)
# ---------------------------------------------------------------------------

REQUEST_ID: ContextKey[str] = ContextKey("request_id")
REQUEST_START_TIME: ContextKey[float] = ContextKey("request_start_time")
REQUEST_METHOD: ContextKey[str] = ContextKey("request_method")
REQUEST_PATH: ContextKey[str] = ContextKey("request_path")
CORRELATION_ID: ContextKey[str] = ContextKey("correlation_id")
CAUSATION_ID: ContextKey[str] = ContextKey("causation_id")
TENANT_ID: ContextKey[str] = ContextKey("tenant_id")
USER_ID: ContextKey[str] = ContextKey("user_id")
TRACE_ID: ContextKey[str] = ContextKey("trace_id")
SPAN_ID: ContextKey[str] = ContextKey("span_id")
TRACE_FLAGS: ContextKey[str] = ContextKey("trace_flags", default="01")

DEFAULT_KEYS: tuple[ContextKey[Any], ...] = (
    REQUEST_ID,
    REQUEST_START_TIME,
    REQUEST_METHOD,
    REQUEST_PATH,
    CORRELATION_ID,
    CAUSATION_ID,
    TENANT_ID,
    USER_ID,
    TRACE_ID,
    SPAN_ID,
    TRACE_FLAGS,
)

__all__ = [
    "CAUSATION_ID",
    "CORRELATION_ID",
    "DEFAULT_KEYS",
    "REQUEST_ID",
    "REQUEST_METHOD",
    "REQUEST_PATH",
    "REQUEST_START_TIME",
    "SPAN_ID",
    "TENANT_ID",
    "TRACE_FLAGS",
    "TRACE_ID",
    "USER_ID",
    "ContextKey",
]
