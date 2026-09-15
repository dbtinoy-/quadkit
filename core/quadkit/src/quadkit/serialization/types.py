"""Type definitions for the serialization subsystem.

Enums and type aliases for JSON backend selection and serializable values.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, TypeAlias


class JSONBackend(StrEnum):
    """Available JSON serialization backends."""

    ORJSON = "orjson"
    STDLIB = "stdlib"


JSONSerializable: TypeAlias = (
    dict[str, Any] | list[Any] | str | int | float | bool | None
)

__all__ = [
    "JSONBackend",
    "JSONSerializable",
]
