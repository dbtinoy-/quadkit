"""Server-Sent Events support for Quadkit Web."""

from __future__ import annotations

from quadkit.web.sse.backpressure import (
    SSEBackpressureHandler,
    SSEConnectionEvents,
    SSEResponse,
    SSERetryTracker,
)
from quadkit.web.sse.decorators import sse_endpoint
from quadkit.web.sse.handler import AbstractSSEHandler
from quadkit.web.sse.heartbeat import SSEHeartbeatScheduler, get_heartbeat_scheduler
from quadkit.web.transport.sse import EventSourceResponse, ServerSentEvent

__all__ = [
    "AbstractSSEHandler",
    "EventSourceResponse",
    "SSEBackpressureHandler",
    "SSEConnectionEvents",
    "SSEHeartbeatScheduler",
    "SSEResponse",
    "SSERetryTracker",
    "ServerSentEvent",
    "get_heartbeat_scheduler",
    "sse_endpoint",
]
