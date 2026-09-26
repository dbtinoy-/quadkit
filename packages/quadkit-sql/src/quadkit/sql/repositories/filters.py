"""Filter operator handlers and registry for repository query filtering."""

from __future__ import annotations

from typing import Any, Protocol


class FilterOperatorHandler(Protocol):
    """Protocol for filter operator handlers."""

    def apply(
        self,
        field: str,
        value: Any,
        params: list[Any],
    ) -> tuple[str, list[Any]]: ...


class GreaterThanHandler:
    """Handler for gt (greater than) operator."""

    def apply(
        self,
        field: str,
        value: Any,
        params: list[Any],
    ) -> tuple[str, list[Any]]:
        return (f"{field} > ?", [*params, value])


class GreaterThanOrEqualHandler:
    """Handler for gte (greater than or equal) operator."""

    def apply(
        self,
        field: str,
        value: Any,
        params: list[Any],
    ) -> tuple[str, list[Any]]:
        return (f"{field} >= ?", [*params, value])


class LessThanHandler:
    """Handler for lt (less than) operator."""

    def apply(
        self,
        field: str,
        value: Any,
        params: list[Any],
    ) -> tuple[str, list[Any]]:
        return (f"{field} < ?", [*params, value])


class LessThanOrEqualHandler:
    """Handler for lte (less than or equal) operator."""

    def apply(
        self,
        field: str,
        value: Any,
        params: list[Any],
    ) -> tuple[str, list[Any]]:
        return (f"{field} <= ?", [*params, value])


class InHandler:
    """Handler for in operator."""

    def apply(
        self,
        field: str,
        value: Any,
        params: list[Any],
    ) -> tuple[str, list[Any]]:
        placeholders = ", ".join("?" for _ in value)
        return (f"{field} IN ({placeholders})", params + list(value))


class ContainsHandler:
    """Handler for contains (LIKE) operator."""

    def apply(
        self,
        field: str,
        value: Any,
        params: list[Any],
    ) -> tuple[str, list[Any]]:
        return (f"{field} LIKE ?", [*params, f"%{value}%"])


class IContainsHandler:
    """Handler for icontains (ILIKE) operator."""

    def apply(
        self,
        field: str,
        value: Any,
        params: list[Any],
    ) -> tuple[str, list[Any]]:
        return (f"{field} ILIKE ?", [*params, f"%{value}%"])


class IsNullHandler:
    """Handler for isnull operator."""

    def apply(
        self,
        field: str,
        value: Any,
        params: list[Any],
    ) -> tuple[str, list[Any]]:
        if value:
            return (f"{field} IS NULL", params)
        return (f"{field} IS NOT NULL", params)


class FilterOperatorRegistry:
    """Registry for filter operator handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, FilterOperatorHandler] = {}

    @classmethod
    def _default_entries(cls) -> dict[str, FilterOperatorHandler]:
        """Declare the built-in filter operator handlers."""
        return {
            "gt": GreaterThanHandler(),
            "gte": GreaterThanOrEqualHandler(),
            "lt": LessThanHandler(),
            "lte": LessThanOrEqualHandler(),
            "in": InHandler(),
            "contains": ContainsHandler(),
            "icontains": IContainsHandler(),
            "isnull": IsNullHandler(),
        }

    @classmethod
    def with_defaults(cls) -> FilterOperatorRegistry:
        """Create a registry pre-populated with the built-in handlers."""
        registry = cls()
        for key, handler in cls._default_entries().items():
            registry.register_handler(key, handler)
        return registry

    def register_handler(self, op: str, handler: FilterOperatorHandler) -> None:
        """Register a filter operator handler."""
        self._handlers[op] = handler

    def apply_operator(
        self,
        op: str,
        field: str,
        value: Any,
        params: list[Any],
    ) -> tuple[str, list[Any]]:
        """Apply a filter operator to a field and value."""
        handler = self._handlers.get(op)
        if handler:
            return handler.apply(field, value, params)
        # Default fallback: equality
        return (f"{field} = ?", [*params, value])

    def get_sqlalchemy_operator(self, op: str) -> Any | None:
        """Get SQLAlchemy-compatible operator (ARC-13).

        Like Laravel's Query Scopes, this allows exposing underlying
        ORM operators if available.
        """
        # Mapping to common SQLAlchemy operators if registry is used with SA
        sa_ops = {
            "gt": lambda c, v: c > v,
            "lt": lambda c, v: c < v,
            "in": lambda c, v: c.in_(v),
            "contains": lambda c, v: c.contains(v),
            "icontains": lambda c, v: c.ilike(v),
        }
        return sa_ops.get(op)
