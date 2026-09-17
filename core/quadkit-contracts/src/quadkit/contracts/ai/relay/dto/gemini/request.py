"""Gemini wire DTO family — request DTO (``GeminiRequest``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.ai.relay.dto.common import require_field
from quadkit.contracts.ai.relay.dto.gemini.parts import GeminiContent


@dataclass(frozen=True)
class GeminiRequest:
    """Gemini ``generateContent`` request body.

    Attributes:
        contents: Conversation turns.
        system_instruction: ``{"parts": [{"text": ...}]}`` or ``None``.
            Serialized as ``systemInstruction``; ``from_dict`` accepts
            both wire casings.
        generation_config: Generation config dict (empty when unset).
            Serialized as ``generationConfig``.
        safety_settings: Safety threshold list, or ``None``.  Serialized
            as ``safetySettings``.
        tools: Tool definitions list, or ``None``.
        tool_config: Tool configuration dict, or ``None``.  Serialized
            as ``toolConfig``.
        passthrough: Unknown fields preserved verbatim.
    """

    contents: list[GeminiContent]
    system_instruction: dict[str, Any] | None = None
    generation_config: dict[str, Any] = field(default_factory=dict)
    safety_settings: list[dict[str, Any]] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_config: dict[str, Any] | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict (camelCase field names)."""
        data: dict[str, Any] = {
            **self.passthrough,
            "contents": [c.to_dict() for c in self.contents],
        }
        if self.system_instruction is not None:
            data["systemInstruction"] = self.system_instruction
        if self.generation_config:
            data["generationConfig"] = self.generation_config
        if self.safety_settings is not None:
            data["safetySettings"] = self.safety_settings
        if self.tools is not None:
            data["tools"] = self.tools
        if self.tool_config is not None:
            data["toolConfig"] = self.tool_config
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeminiRequest:
        """Build a request from a wire dict, capturing unknown keys.

        ``systemInstruction`` and ``generationConfig`` are the canonical
        wire keys; snake_case ``system_instruction`` is accepted for
        compatibility.

        Raises:
            RelayError: With code ``malformed_payload`` when ``contents``
                is absent.
        """
        known = {
            "contents",
            "systemInstruction",
            "system_instruction",
            "generationConfig",
            "safetySettings",
            "tools",
            "toolConfig",
        }
        system = data.get("systemInstruction", data.get("system_instruction"))
        return cls(
            contents=[
                GeminiContent.from_dict(c) for c in require_field(data, "contents")
            ],
            system_instruction=system,
            generation_config=data.get("generationConfig", {}),
            safety_settings=data.get("safetySettings"),
            tools=data.get("tools"),
            tool_config=data.get("toolConfig"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )
