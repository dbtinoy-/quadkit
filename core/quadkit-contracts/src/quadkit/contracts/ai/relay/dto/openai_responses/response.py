"""OpenAI Responses wire DTO family — response DTOs, usage and events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.ai.relay.dto.common import require_field
from quadkit.contracts.ai.relay.dto.items import ResponsesItem


@dataclass(frozen=True)
class ResponsesUsage:
    """OpenAI Responses usage accounting.

    Attributes:
        prompt_tokens: Chat-style prompt token count.
        completion_tokens: Chat-style completion token count.
        total_tokens: Explicit totals (can differ from prompt + completion).
        prompt_tokens_details: Cache details (relaykit serializes a
            zero-value prompt_tokens_details dict even when empty).
        completion_tokens_details: Reasoning/details count (relaykit
            serializes it even when empty).
        input_tokens: Source input count carried into chat emission.
        input_tokens_details: Raw input token details per ``input_tokens``.
        output_tokens: Source output count carried into chat emails.
        output_tokens_details: Legacy capture of the raw output details
            (never serialized; relaykit emits ``completion_tokens_details``).
        passthrough: Unknown fields preserved verbatim.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_tokens_details: dict[str, Any] | None = None
    completion_tokens_details: dict[str, Any] | None = None
    input_tokens: int = 0
    input_tokens_details: dict[str, Any] | None = None
    output_tokens: int = 0
    output_tokens_details: dict[str, Any] | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, mirroring relaykit's always-on usage."""
        data: dict[str, Any] = {
            **self.passthrough,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens
            or (self.input_tokens + self.output_tokens),
            "prompt_tokens_details": self.prompt_tokens_details or {"cached_tokens": 0},
            "completion_tokens_details": self.completion_tokens_details
            or {"reasoning_tokens": 0},
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }
        if self.input_tokens_details is not None:
            data["input_tokens_details"] = self.input_tokens_details
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResponsesUsage:
        """Build usage from a wire dict, capturing unknown keys."""
        known = {
            "input_tokens",
            "input_tokens_details",
            "output_tokens",
            "output_tokens_details",
            "total_tokens",
            "prompt_tokens_details",
            "completion_tokens_details",
            "prompt_tokens",
            "completion_tokens",
        }
        return cls(
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            prompt_tokens_details=data.get("prompt_tokens_details"),
            completion_tokens_details=data.get("completion_tokens_details"),
            input_tokens=data.get("input_tokens", 0),
            input_tokens_details=data.get("input_tokens_details"),
            output_tokens=data.get("output_tokens", 0),
            output_tokens_details=data.get("output_tokens_details"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class ResponsesIncompleteDetails:
    """Why a Responses response is incomplete.

    Attributes:
        reason: ``max_output_tokens``, ``content_filter``, etc.
        passthrough: Unknown fields preserved verbatim.
    """

    reason: str | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {**self.passthrough}
        if self.reason is not None:
            data["reason"] = self.reason
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResponsesIncompleteDetails:
        """Build details from a wire dict, capturing unknown keys."""
        known = {"reason"}
        return cls(
            reason=data.get("reason"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class ResponsesResponse:
    """OpenAI Responses non-streamed response body.

    Attributes:
        id: Response id.
        model: Model name.
        output: Output items (messages, function calls, reasoning).
        object: Object type (``response``).
        created_at: Unix timestamp.
        status: ``completed``, ``in_progress``, ``incomplete``, ``failed``.
        incomplete_details: Why the response is incomplete, or ``None``.
        error: Error object for failed responses, or ``None``.
        usage: Typed usage, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    id: str
    model: str
    output: list[ResponsesItem]
    object: str = "response"
    created_at: int = 0
    status: str | None = None
    incomplete_details: ResponsesIncompleteDetails | None = None
    error: dict[str, Any] | None = None
    usage: ResponsesUsage | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict.

        Relaykit's Go response structs always serialize the optional
        request-style fields (``instructions``, ``temperature``, ...) as
        explicit nulls/zeros, so this mirrors that shape.
        """
        data: dict[str, Any] = {
            **self.passthrough,
            "id": self.id,
            "object": self.object,
            "created_at": self.created_at,
            "status": self.status or "completed",
            "instructions": None,
            "max_output_tokens": 0,
            "model": self.model,
            "output": [i.to_dict() for i in self.output],
            "parallel_tool_calls": False,
            "previous_response_id": None,
            "reasoning": None,
            "store": False,
            "temperature": 0,
            "tool_choice": None,
            "tools": None,
            "top_p": 0,
            "truncation": None,
        }
        if self.incomplete_details is not None:
            data["incomplete_details"] = self.incomplete_details.to_dict()
        if self.error is not None:
            data["error"] = self.error
        if self.usage is not None:
            data["usage"] = self.usage.to_dict()
        data["user"] = None
        data["metadata"] = None
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResponsesResponse:
        """Build a response from a wire dict, capturing unknown keys.

        Raises:
            RelayError: With code ``malformed_payload`` when ``id`` or
                ``model`` is absent.
        """
        known = {
            "id",
            "object",
            "created_at",
            "model",
            "output",
            "status",
            "incomplete_details",
            "error",
            "usage",
        }
        incomplete = data.get("incomplete_details")
        usage = data.get("usage")
        return cls(
            id=require_field(data, "id"),
            object=data.get("object", "response"),
            created_at=data.get("created_at", 0),
            model=require_field(data, "model"),
            output=[ResponsesItem.from_dict(i) for i in data.get("output", [])],
            status=data.get("status"),
            incomplete_details=(
                ResponsesIncompleteDetails.from_dict(incomplete)
                if isinstance(incomplete, dict)
                else None
            ),
            error=data.get("error"),
            usage=ResponsesUsage.from_dict(usage) if isinstance(usage, dict) else None,
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class ResponsesEvent:
    """One SSE event in the Responses stream lifecycle.

    The ``type`` field is the discriminator (``response.created``,
    ``response.output_item.added``, ``response.content_part.added``,
    ``response.output_text.delta``, ``response.output_text.done``,
    ``response.content_part.done``, ``response.output_item.done``,
    ``response.function_call_arguments.delta``,
    ``response.function_call_arguments.done``,
    ``response.reasoning_summary_text.delta``,
    ``response.reasoning_summary_text.done``, ``response.completed``,
    ``response.incomplete``, ``response.failed``, ``response.error``).

    Attributes:
        type: Event type discriminator.
        sequence_number: Monotonic event sequence number.
        response: Snapshot on ``response.*`` lifecycle events, or ``None``.
        item: Item on ``output_item.*`` events, or ``None``.
        item_id: Id of the item an event describes, or ``None``.
        output_index: Output item index, or ``None``.
        content_index: Content part index, or ``None``.
        part: Raw content part on ``content_part.*`` events, or ``None``.
        delta: Text/arguments delta, or ``None``.
        error: Raw error payload, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    type: str
    sequence_number: int = 0
    response: ResponsesResponse | None = None
    item: ResponsesItem | None = None
    item_id: str | None = None
    output_index: int | None = None
    content_index: int | None = None
    part: dict[str, Any] | None = None
    delta: str | None = None
    error: dict[str, Any] | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict as the Responses SSE envelope.

        Relaykit frames each stream event as ``{"Type": <type>, "Payload":
        <fields>}`` — the ``Type`` is the SSE ``event`` name and ``Payload``
        is the JSON body (which repeats the ``type`` discriminator).
        """
        payload: dict[str, Any] = {**self.passthrough, "type": self.type}
        if self.sequence_number:
            payload["sequence_number"] = self.sequence_number
        if self.response is not None:
            payload["response"] = self.response.to_dict()
        if self.item is not None:
            payload["item"] = self.item.to_dict()
        if self.item_id is not None:
            payload["item_id"] = self.item_id
        if self.output_index is not None:
            payload["output_index"] = self.output_index
        if self.content_index is not None:
            payload["content_index"] = self.content_index
        if self.part is not None:
            payload["part"] = self.part
        if self.delta is not None:
            payload["delta"] = self.delta
        if self.error is not None:
            payload["error"] = self.error
        return {"Type": self.type, "Payload": payload}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResponsesEvent:
        """Build an event from a wire dict, capturing unknown keys.

        Accepts both the SSE envelope (``Payload``) and the bare payload.
        """
        source = data.get("Payload")
        if isinstance(source, dict):
            data = source
        known = {
            "type",
            "sequence_number",
            "response",
            "item",
            "item_id",
            "output_index",
            "content_index",
            "part",
            "delta",
            "error",
        }
        response = data.get("response")
        item = data.get("item")
        return cls(
            type=data.get("type", "response.in_progress"),
            sequence_number=data.get("sequence_number", 0),
            response=(
                ResponsesResponse.from_dict(response)
                if isinstance(response, dict)
                else None
            ),
            item=ResponsesItem.from_dict(item) if isinstance(item, dict) else None,
            item_id=data.get("item_id"),
            output_index=data.get("output_index"),
            content_index=data.get("content_index"),
            part=data.get("part"),
            delta=data.get("delta"),
            error=data.get("error"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )
