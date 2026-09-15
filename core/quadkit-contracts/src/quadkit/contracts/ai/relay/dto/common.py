"""Shared JSON helpers for the relay wire DTO families.

The four protocol DTO families (OpenAI Chat, OpenAI Responses, Claude,
and Gemini) all carry raw wire fields as JSON-ish dictionaries and
preserve unknown upstream fields verbatim in ``passthrough``.  This
module owns those shared aliases and helpers so each family keeps the
same present/wire semantics without redefining them.
"""

from __future__ import annotations

from typing import Any, TypeAlias

from quadkit.contracts.ai.exceptions import RelayError, RelayErrorCode

__all__ = [
    "JsonDict",
    "JsonValue",
    "require_field",
]


JsonValue: TypeAlias = dict[str, Any] | list[Any] | str | int | float | bool | None
"""A JSON-compatible value accepted by the wire DTOs."""

JsonDict: TypeAlias = dict[str, JsonValue]
"""A JSON-compatible object (wire request/response fragment)."""


def require_field(data: dict[str, Any], name: str) -> Any:
    """Return a required wire field or raise a typed malformed-payload error.

    Args:
        data: Raw wire dict being parsed.
        name: Name of the required field.

    Returns:
        The field value.

    Raises:
        RelayError: With code ``malformed_payload`` when the field is
            absent or ``None``.
    """
    if name not in data or data[name] is None:
        raise RelayError(
            f"malformed payload: missing required field '{name}'",
            code=RelayErrorCode.MALFORMED_PAYLOAD,
        )
    return data[name]
