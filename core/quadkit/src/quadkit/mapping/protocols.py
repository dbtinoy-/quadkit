from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class TypeConverterProtocol(Protocol):
    """Converts a value from one type to another."""

    def can_convert(self, source_type: type, target_type: type) -> bool: ...
    def convert(self, value: Any, target_type: type) -> Any: ...
