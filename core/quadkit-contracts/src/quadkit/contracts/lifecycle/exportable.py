from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ExportableProtocol(Protocol):
    """Protocol for data export."""

    async def export_data(
        self,
        file_format: str,
        filters: dict[str, Any] | None = None,
        fields: list[str] | None = None,
    ) -> bytes: ...

    def get_supported_formats(self) -> list[str]: ...


__all__ = ["ExportableProtocol"]
