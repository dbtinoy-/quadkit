"""OpenAI Responses wire DTO family — shared response/request items.

Lives at the ``dto`` level (not under ``openai_responses``) so the
module path stays within the 6-segment import-depth gate; the
``openai_responses`` package re-exports ``ResponsesItem`` for the
canonical public API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ResponsesItem:
    """An item in a Responses request ``input`` or response ``output``.

    Attributes:
        type: ``message``, ``function_call``, ``function_call_output``,
            ``reasoning``, ``web_search_call``.
        role: ``user`` / ``assistant`` for message items.
        content: Message content list, or ``None``.
        id: Item id, or ``None``.
        call_id: Function call id, or ``None``.
        name: Function name, or ``None``.
        arguments: Function call arguments string, or ``None``.
        output: Function call output string, or ``None``.
        summary: Reasoning summary for ``reasoning`` items, or ``None``.
        status: Output item status (``completed`` / ``incomplete``).
        quality: Output item quality (relaykit always serializes ``""``).
        size: Output item size (relaykit always serializes ``""``).
        passthrough: Unknown fields preserved verbatim.
    """

    type: str | None = None
    role: str | None = None
    content: str | list[dict[str, Any]] | None = None
    id: str | None = None
    call_id: str | None = None
    name: str | None = None
    arguments: str | None = None
    output: str | None = None
    summary: list[dict[str, Any]] | None = None
    status: str | None = None
    quality: str | None = None
    size: str | None = None
    passthrough: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to wire dict.

        Output items (those carrying a ``status``) always serialize
        ``content`` (relaykit uses no ``omitempty`` on it, so function
        calls carry an explicit ``null``) plus the ``status``,
        ``quality``, and ``size`` fields relaykit Go structs always
        render. Input request items never render a ``content`` key for
        function calls.
        """
        data: dict[str, Any] = {**self.passthrough}
        if self.type is not None:
            data["type"] = self.type
        if self.role is not None:
            data["role"] = self.role
        if (
            self.type == "function_call" and self.status is not None
        ) or self.content is not None:
            data["content"] = self.content
        if self.status is not None:
            data["status"] = self.status
        if self.quality is not None:
            data["quality"] = self.quality
        if self.size is not None:
            data["size"] = self.size
        if self.id is not None:
            data["id"] = self.id
        if self.call_id is not None:
            data["call_id"] = self.call_id
        if self.name is not None:
            data["name"] = self.name
        if self.arguments is not None:
            data["arguments"] = self.arguments
        if self.output is not None:
            data["output"] = self.output
        if self.summary is not None:
            data["summary"] = self.summary
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResponsesItem:
        """Build an item from a wire dict, capturing unknown keys."""
        known = {
            "type",
            "role",
            "content",
            "id",
            "call_id",
            "name",
            "arguments",
            "output",
            "summary",
            "status",
            "quality",
            "size",
        }
        return cls(
            type=data.get("type", "message"),
            role=data.get("role"),
            content=data.get("content"),
            id=data.get("id"),
            call_id=data.get("call_id"),
            name=data.get("name"),
            arguments=data.get("arguments"),
            output=data.get("output"),
            summary=data.get("summary"),
            status=data.get("status"),
            quality=data.get("quality"),
            size=data.get("size"),
            passthrough={k: v for k, v in data.items() if k not in known},
        )
