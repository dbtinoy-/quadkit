"""Request log contracts for the relay gateway.

A request-log entry carries dispatch metadata only — never prompts,
tool arguments, media bytes, or credential-bearing headers.  The write
protocol is the framework boundary: the gateway only emits entries and
implementations (durable stores) never import the gateway.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RelayRequestLogEntry:
    """One gateway request dispatch, redaction-safe."""

    request_id: str
    user_id: str
    token_id: str
    endpoint_kind: str
    model: str
    channel_name: str
    status: str  # completed | failed | cancelled | rate_limited | unauthorized
    created_at: datetime  # set by the emitter at completion
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: str = "0"  # Decimal string, units match relay billing estimation
    latency_ms: int = 0
    error_code: str = ""


@runtime_checkable
class RelayRequestLogStoreProtocol(Protocol):
    """Best-effort durable request-log sink.

    Implementations must not raise to callers; the gateway treats any
    store failure as a warning-only event.
    """

    async def append(self, entry: RelayRequestLogEntry) -> None: ...


__all__ = ["RelayRequestLogEntry", "RelayRequestLogStoreProtocol"]
