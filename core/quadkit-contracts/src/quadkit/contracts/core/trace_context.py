"""Trace context variables for distributed tracing.

Provides context variables for trace_id, span_id, and trace_flags
following W3C Trace Context specification.
"""

from __future__ import annotations

import contextvars
import secrets

trace_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_id",
    default=None,
)
span_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "span_id",
    default=None,
)
trace_flags_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_flags",
    default=None,
)


def new_trace_id() -> str:
    """Generate a new trace ID (32 hex chars)."""
    return secrets.token_hex(16)


def new_span_id() -> str:
    """Generate a new span ID (16 hex chars)."""
    return secrets.token_hex(8)


__all__ = [
    "new_span_id",
    "new_trace_id",
    "span_id_var",
    "trace_flags_var",
    "trace_id_var",
]
