"""OpenAI ``/v1/responses`` wire DTO family.

Field names follow the OpenAI API snake_case wire format; the DTO layer
accepts documented camelCase aliases only where noted.

Modules are split for the 500-LOC ratchet; import from this package
for the canonical top-level names."""

from __future__ import annotations

from quadkit.contracts.ai.relay.dto.items import ResponsesItem
from quadkit.contracts.ai.relay.dto.openai_responses.request import ResponsesRequest
from quadkit.contracts.ai.relay.dto.openai_responses.response import (
    ResponsesEvent,
    ResponsesIncompleteDetails,
    ResponsesResponse,
    ResponsesUsage,
)

__all__ = [
    "ResponsesEvent",
    "ResponsesIncompleteDetails",
    "ResponsesItem",
    "ResponsesRequest",
    "ResponsesResponse",
    "ResponsesUsage",
]
