"""Wire transport contracts for the relay gateway.

Defines the upstream request/response/chunk value types and the upstream
client protocol used by the relay gateway to talk to model providers.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from quadkit.contracts.ai.relay.types import JsonValue


@dataclass(frozen=True, slots=True)
class UpstreamRequest:
    """A fully-resolved request to an upstream model provider.

    Attributes:
        request_id: Identifier of the originating gateway request.
        method: HTTP method used for the upstream call.
        url: Fully-resolved upstream endpoint URL.
        headers: Headers to send with the upstream call.
        payload: JSON payload to send with the upstream call.
        timeout_seconds: Timeout budget for the upstream call.
        channel_name: Name of the relay channel that selected this call. Empty
            when the caller does not use channel identity.
    """

    request_id: str
    method: str
    url: str
    headers: Mapping[str, str]
    payload: Mapping[str, JsonValue]
    timeout_seconds: float
    channel_name: str = ""


@dataclass(frozen=True, slots=True)
class UpstreamResponse:
    """A non-streaming response from an upstream model provider."""

    status_code: int
    headers: Mapping[str, str]
    payload: Mapping[str, JsonValue] | None


@dataclass(frozen=True, slots=True)
class UpstreamChunk:
    """A single streaming chunk from an upstream model provider."""

    event: str | None
    data: str
    terminal: bool = False


@dataclass(frozen=True, slots=True)
class RelayWireEvent:
    """A normalized streaming event emitted by the relay gateway."""

    event: str | None
    data: Mapping[str, JsonValue] | None
    terminal: bool = False


@runtime_checkable
class RelayUpstreamProtocol(Protocol):
    """Client protocol for invoking upstream model providers."""

    async def request(self, request: UpstreamRequest) -> UpstreamResponse: ...
    async def stream(
        self, request: UpstreamRequest
    ) -> AsyncIterator[UpstreamChunk]: ...
    async def cancel(self, request_id: str) -> None: ...
