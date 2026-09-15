"""W3C Trace Context (traceparent) utilities for Quadkit Web.

This module provides utilities for parsing and generating W3C traceparent headers,
enabling distributed tracing across web services.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from quadkit.contracts.core.trace_context import (
    span_id_var,
    trace_flags_var,
    trace_id_var,
)

if TYPE_CHECKING:
    from quadkit.primitives.context import RequestContext

# W3C Traceparent Regex: version-traceid-spanid-flags
# trace-id (32 hex), span-id (16 hex), flags (2 hex)
TRACEPARENT_REGEX = re.compile(
    r"^[0-9a-f]{2}-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$",
)


def extract_traceparent(header: str) -> dict[str, str] | None:
    """Parse W3C traceparent header.

    Returns a dict with trace_id, parent_id, and trace_flags if valid.
    """
    match = TRACEPARENT_REGEX.match(header.strip())
    if match:
        return {
            "trace_id": match.group(1),
            "parent_id": match.group(2),
            "trace_flags": match.group(3),
        }
    return None


def inject_traceparent() -> str | None:
    """Generate W3C traceparent header from current core context."""
    trace_id = trace_id_var.get(None)
    span_id = span_id_var.get(None)
    flags = trace_flags_var.get(None) or "01"

    if trace_id and span_id:
        return f"00-{trace_id}-{span_id}-{flags}"
    return None


def load_trace_to_context(ctx: RequestContext, header: str | None) -> None:
    """Load trace context from W3C traceparent header into a RequestContext in-memory."""
    if not header:
        return
    data = extract_traceparent(header)
    if data:
        ctx.trace_id = data["trace_id"]
        ctx.trace_flags = data["trace_flags"]


__all__ = [
    "TRACEPARENT_REGEX",
    "extract_traceparent",
    "inject_traceparent",
    "load_trace_to_context",
]
