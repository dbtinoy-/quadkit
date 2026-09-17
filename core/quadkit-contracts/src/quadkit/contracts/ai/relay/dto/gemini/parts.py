"""Gemini wire DTO family — content parts (``GeminiPart``/``GeminiContent``)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GeminiPart:
    """A part inside a Gemini content.

    Attributes:
        text: Text payload, or ``None``.
        inline_data: ``{"mime_type": ..., "data": base64}`` or ``None``.
        file_data: ``{"mime_type": ..., "file_uri": ...}`` or ``None``
            (already-resolved file reference).
        function_call: ``{"name": ..., "args": {...}}`` or ``None``.
        function_response: ``{"name": ..., "response": {...}}`` or ``None``.
        thought: Whether this is a thinking part.
        thought_signature: Thought signature for thinking parts, or ``None``.
        passthrough: Unknown fields preserved verbatim.
    """

    text: str | None = None
    inline_data: dict[str, Any] | None = None
    file_data: dict[str, Any] | None = None
    function_call: dict[str, Any] | None = None
    function_response: dict[str, Any] | None = None
    thought: bool = False
    thought_signature: str | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict (camelCase field names)."""
        data: dict[str, Any] = {**self.passthrough}
        if self.text is not None:
            data["text"] = self.text
        if self.inline_data is not None:
            data["inlineData"] = self.inline_data
        if self.file_data is not None:
            data["fileData"] = self.file_data
        if self.function_call is not None:
            data["functionCall"] = self.function_call
        if self.function_response is not None:
            data["functionResponse"] = self.function_response
        if self.thought:
            data["thought"] = True
        if self.thought_signature is not None:
            data["thoughtSignature"] = self.thought_signature
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeminiPart:
        """Build a part from a wire dict, capturing unknown keys."""
        known = {
            "text",
            "inlineData",
            "fileData",
            "functionCall",
            "functionResponse",
            "thought",
            "thoughtSignature",
        }
        return cls(
            text=data.get("text"),
            inline_data=data.get("inlineData"),
            file_data=data.get("fileData"),
            function_call=data.get("functionCall"),
            function_response=data.get("functionResponse"),
            thought=bool(data.get("thought", False)),
            thought_signature=data.get("thoughtSignature"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )


@dataclass(frozen=True)
class GeminiContent:
    """One content turn in Gemini format.

    Attributes:
        role: ``user``, ``model``, ``function``.
        parts: Content parts.
    """

    role: str
    parts: list[GeminiPart]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict."""
        return {"role": self.role, "parts": [p.to_dict() for p in self.parts]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GeminiContent:
        """Build a content from a wire dict."""
        return cls(
            role=data.get("role", "user"),
            parts=[GeminiPart.from_dict(p) for p in data.get("parts", [])],
        )
