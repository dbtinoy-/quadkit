"""OpenAI Responses wire DTO family — request DTO (``ResponsesRequest``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.ai.relay.dto.common import require_field
from quadkit.contracts.ai.relay.dto.items import ResponsesItem


@dataclass(frozen=True)
class ResponsesRequest:
    """OpenAI Responses request body.

    Attributes:
        model: Model name.
        input: List of items, or a plain string.
        instructions: System instructions, or ``None``.
        tools: Tool definitions, or ``None``.
        temperature: Sampling temperature, or ``None``.
        max_output_tokens: Max output tokens, or ``None``.
        stream: Whether the caller wants a stream.
        include: Extra top-level fields to include, or ``None``.
        parallel_tool_calls: Parallel tool-call flag, or ``None``.
        reasoning: Reasoning config (e.g. ``{"effort": ...}``), or ``None``.
        text: Response-format config, or ``None``.
        service_tier: Service tier, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    model: str
    input: list[ResponsesItem] | str
    instructions: str | None = None
    tools: list[dict[str, Any]] | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    stream: bool = False
    include: list[str] | None = None
    parallel_tool_calls: bool | None = None
    reasoning: dict[str, Any] | None = None
    text: dict[str, Any] | None = None
    service_tier: str | None = None
    tool_choice: Any | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict, omitting ``None`` optional fields."""
        data: dict[str, Any] = {**self.passthrough, "model": self.model}
        if isinstance(self.input, str):
            data["input"] = self.input
        else:
            data["input"] = [i.to_dict() for i in self.input]
        if self.instructions is not None:
            data["instructions"] = self.instructions
        if self.tools is not None:
            data["tools"] = self.tools
        if self.temperature is not None:
            data["temperature"] = self.temperature
        if self.max_output_tokens is not None:
            data["max_output_tokens"] = self.max_output_tokens
        data["stream"] = self.stream
        if self.include is not None:
            data["include"] = self.include
        if self.parallel_tool_calls is not None:
            data["parallel_tool_calls"] = self.parallel_tool_calls
        if self.reasoning is not None:
            data["reasoning"] = self.reasoning
        if self.text is not None:
            data["text"] = self.text
        if self.service_tier is not None:
            data["service_tier"] = self.service_tier
        if self.tool_choice is not None:
            data["tool_choice"] = self.tool_choice
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResponsesRequest:
        """Build a request from a wire dict, capturing unknown keys.

        Raises:
            RelayError: With code ``malformed_payload`` when ``model``
                is absent.
        """
        known = {
            "model",
            "input",
            "instructions",
            "tools",
            "temperature",
            "max_output_tokens",
            "stream",
            "include",
            "parallel_tool_calls",
            "reasoning",
            "text",
            "service_tier",
            "tool_choice",
        }
        raw_input = data.get("input", [])
        return cls(
            model=require_field(data, "model"),
            input=(
                raw_input
                if isinstance(raw_input, str)
                else [ResponsesItem.from_dict(i) for i in raw_input]
            ),
            instructions=data.get("instructions"),
            tools=data.get("tools"),
            temperature=data.get("temperature"),
            max_output_tokens=data.get("max_output_tokens"),
            stream=bool(data.get("stream", False)),
            include=data.get("include"),
            parallel_tool_calls=data.get("parallel_tool_calls"),
            reasoning=data.get("reasoning"),
            text=data.get("text"),
            service_tier=data.get("service_tier"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )
