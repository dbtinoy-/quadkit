"""Relay protocol conversion shared types.

This package holds the canonical intermediate representation (IR), wire
DTOs, conversion context, and service protocols shared by the converter
engine implemented in the ``quadkit-ai-relay`` extension package.
"""

from __future__ import annotations

from quadkit.contracts.ai.relay.auth import (
    RelayAuthError,
    RelayAuthIdentity,
    RelayAuthVerifierProtocol,
)
from quadkit.contracts.ai.relay.context import (
    ClaudeOptions,
    GeminiOptions,
    MediaResolverProtocol,
    RelayConversionContext,
    RelayOptions,
)
from quadkit.contracts.ai.relay.dto import (
    ClaudeContent,
    ClaudeMessage,
    ClaudeRequest,
    ClaudeResponse,
    GeminiContent,
    GeminiPart,
    GeminiRequest,
    OpenAIChatMessage,
    OpenAIChatRequest,
    OpenAIChatResponse,
    ResponsesItem,
    ResponsesRequest,
    ResponsesResponse,
)
from quadkit.contracts.ai.relay.gateway import (
    RelayChannel,
    RelayGatewayError,
    RelayGatewayMetadata,
    RelayGatewayProtocol,
    RelayGatewayRequest,
    RelayGatewayResult,
)
from quadkit.contracts.ai.relay.ir import (
    RelayRequest,
    RelayResponse,
    StreamDelta,
    StreamState,
)
from quadkit.contracts.ai.relay.ledger import (
    RelayCheckinRecord,
    RelayLedgerError,
    RelayLedgerServiceProtocol,
    RelayTopUpRecord,
    RelayTopUpStatus,
)
from quadkit.contracts.ai.relay.logs import (
    RelayRequestLogEntry,
    RelayRequestLogStoreProtocol,
)
from quadkit.contracts.ai.relay.operations import (
    RelayActiveStream,
    RelayChannelHealth,
    RelayOperationsControlProtocol,
    RelayOperationsProtocol,
    RelayPolicyChange,
    RelayPolicySnapshot,
    RelayPolicyStoreProtocol,
    RelayRegistryDiagnostics,
    RelayRouteMetrics,
    TimeWindow,
)
from quadkit.contracts.ai.relay.protocols import (
    RelayConverterProtocol,
    RelayMapperProtocol,
    RelayRegistryProtocol,
    RelayStreamOptions,
    RelayStreamSessionProtocol,
)
from quadkit.contracts.ai.relay.ratelimit import (
    RelayRateLimitCounterProtocol,
    RelayRateLimitDecision,
)
from quadkit.contracts.ai.relay.store import (
    RelayChannelSnapshot,
    RelayChannelStoreProtocol,
)
from quadkit.contracts.ai.relay.transport import (
    RelayUpstreamProtocol,
    RelayWireEvent,
    UpstreamChunk,
    UpstreamRequest,
    UpstreamResponse,
)
from quadkit.contracts.ai.relay.types import (
    ConversionQuality,
    JsonObject,
    JsonValue,
    RelayConvertResult,
    RelayFormat,
    RelayLoss,
    RelayRequestPayload,
    RelayResponsePayload,
    RelayUsage,
)
from quadkit.contracts.ai.relay.usage import (
    RelayDailyUsage,
    RelayModelRank,
    RelayUsageServiceProtocol,
)

__all__ = [
    "ClaudeContent",
    "ClaudeMessage",
    "ClaudeOptions",
    "ClaudeRequest",
    "ClaudeResponse",
    "ConversionQuality",
    "GeminiContent",
    "GeminiOptions",
    "GeminiPart",
    "GeminiRequest",
    "JsonObject",
    "JsonValue",
    "MediaResolverProtocol",
    "OpenAIChatMessage",
    "OpenAIChatRequest",
    "OpenAIChatResponse",
    "RelayActiveStream",
    "RelayAuthError",
    "RelayAuthIdentity",
    "RelayAuthVerifierProtocol",
    "RelayChannel",
    "RelayChannelHealth",
    "RelayChannelSnapshot",
    "RelayChannelStoreProtocol",
    "RelayCheckinRecord",
    "RelayConversionContext",
    "RelayConvertResult",
    "RelayConverterProtocol",
    "RelayDailyUsage",
    "RelayFormat",
    "RelayGatewayError",
    "RelayGatewayMetadata",
    "RelayGatewayProtocol",
    "RelayGatewayRequest",
    "RelayGatewayResult",
    "RelayLedgerError",
    "RelayLedgerServiceProtocol",
    "RelayLoss",
    "RelayMapperProtocol",
    "RelayModelRank",
    "RelayOperationsControlProtocol",
    "RelayOperationsProtocol",
    "RelayOptions",
    "RelayPolicyChange",
    "RelayPolicySnapshot",
    "RelayPolicyStoreProtocol",
    "RelayRateLimitCounterProtocol",
    "RelayRateLimitDecision",
    "RelayRegistryDiagnostics",
    "RelayRegistryProtocol",
    "RelayRequest",
    "RelayRequestLogEntry",
    "RelayRequestLogStoreProtocol",
    "RelayRequestPayload",
    "RelayResponse",
    "RelayResponsePayload",
    "RelayRouteMetrics",
    "RelayStreamOptions",
    "RelayStreamSessionProtocol",
    "RelayUpstreamProtocol",
    "RelayUsage",
    "RelayUsageServiceProtocol",
    "RelayWireEvent",
    "ResponsesItem",
    "ResponsesRequest",
    "ResponsesResponse",
    "StreamDelta",
    "StreamState",
    "TimeWindow",
    "UpstreamChunk",
    "UpstreamRequest",
    "UpstreamResponse",
]
