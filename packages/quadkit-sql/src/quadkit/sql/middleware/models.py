from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QueryContext:
    """Context passed through the middleware pipeline."""

    sql: str
    params: Any = None
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    result: Any = None
    error: Exception | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
