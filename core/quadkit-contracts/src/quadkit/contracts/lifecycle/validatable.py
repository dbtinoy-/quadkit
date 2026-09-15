from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ValidatableProtocol(Protocol):
    """Protocol for data validation."""

    async def validate_record(
        self,
        record: dict[str, Any],
        operation: str = "create",
    ) -> dict[str, Any]: ...

    def get_validation_rules(self) -> dict[str, Any]: ...


__all__ = ["ValidatableProtocol"]
