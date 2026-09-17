"""Registry for OpenAPI type documenters."""

from __future__ import annotations

from typing import Any, Protocol


class TypeDocumenterProtocol(Protocol):
    """Protocol for type documenters."""

    def can_document(self, annotation: Any) -> bool:
        """Check if this documenter can handle the given annotation."""
        ...

    def document(self, parameter: dict[str, Any]) -> None:
        """Apply documentation schema to the parameter."""
        ...


class IntDocumenter:
    """Documenter for integer types."""

    def can_document(self, annotation: Any) -> bool:
        return annotation is int

    def document(self, parameter: dict[str, Any]) -> None:
        parameter["schema"] = {"type": "integer"}


class BoolDocumenter:
    """Documenter for boolean types."""

    def can_document(self, annotation: Any) -> bool:
        return annotation is bool

    def document(self, parameter: dict[str, Any]) -> None:
        parameter["schema"] = {"type": "boolean"}


class FloatDocumenter:
    """Documenter for float types."""

    def can_document(self, annotation: Any) -> bool:
        return annotation is float

    def document(self, parameter: dict[str, Any]) -> None:
        parameter["schema"] = {"type": "number"}


class StringDocumenter:
    """Documenter for string types (default)."""

    def can_document(self, annotation: Any) -> bool:
        return annotation is str

    def document(self, parameter: dict[str, Any]) -> None:
        parameter["schema"] = {"type": "string"}


class TypeDocumenterRegistry:
    """Registry for type documenters."""

    def __init__(self) -> None:
        self._documenters: list[TypeDocumenterProtocol] = [
            IntDocumenter(),
            BoolDocumenter(),
            FloatDocumenter(),
            StringDocumenter(),
        ]

    def get_documenter(self, annotation: Any) -> TypeDocumenterProtocol | None:
        """Find a documenter for the given annotation."""
        for documenter in self._documenters:
            if documenter.can_document(annotation):
                return documenter
        return None


_type_documenter_registry = TypeDocumenterRegistry()
