"""Entity operations, handlers, and registries for SimpleUnitOfWork."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, cast

from quadkit.contracts import DatabaseProviderProtocol
from quadkit.logging import get_logger
from quadkit.sql.lib import entity_to_dict

logger = get_logger(__name__)


@dataclass
class EntityOperation:
    """Represents a pending SQL operation on an entity."""

    entity: Any
    operation_type: str  # 'insert', 'update', 'delete'
    table_name: str
    primary_key: str | None = None


# ---------------------------------------------------------------------------
# Operation handlers
# ---------------------------------------------------------------------------


class InsertOperationHandler:
    """Handler for insert operations."""

    async def execute(
        self,
        operation: EntityOperation,
        provider: DatabaseProviderProtocol,
    ) -> None:
        """Execute an insert operation."""
        data = _entity_to_dict(operation.entity)
        result = await provider.execute_insert(table=operation.table_name, data=data)
        if not result.success:
            raise RuntimeError(f"Insert failed: {result.error_message}")


class UpdateOperationHandler:
    """Handler for update operations."""

    async def execute(
        self,
        operation: EntityOperation,
        provider: DatabaseProviderProtocol,
    ) -> None:
        """Execute an update operation."""
        data = _entity_to_dict(operation.entity)
        entity_id = getattr(operation.entity, "id", None)
        if entity_id is None:
            raise ValueError("Entity must have an 'id' attribute for updates")
        result = await provider.execute_update(
            table=operation.table_name,
            data=data,
            where_clause="id = ?",
            where_params=[entity_id],
        )
        if not result.success:
            raise RuntimeError(f"Update failed: {result.error_message}")


class DeleteOperationHandler:
    """Handler for delete operations."""

    async def execute(
        self,
        operation: EntityOperation,
        provider: DatabaseProviderProtocol,
    ) -> None:
        """Execute a delete operation."""
        entity_id = getattr(operation.entity, "id", None)
        if entity_id is None:
            raise ValueError("Entity must have an 'id' attribute for deletes")
        result = await provider.execute_delete(
            table=operation.table_name,
            where_clause="id = ?",
            where_params=[entity_id],
        )
        if not result.success:
            raise RuntimeError(f"Delete failed: {result.error_message}")


class OperationHandlerRegistry:
    """Registry for SQL operation handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, Any] = {}

    @classmethod
    def _default_entries(cls) -> dict[str, Any]:
        """Declare the built-in operation handlers."""
        return {
            "insert": InsertOperationHandler(),
            "update": UpdateOperationHandler(),
            "delete": DeleteOperationHandler(),
        }

    @classmethod
    def with_defaults(cls) -> OperationHandlerRegistry:
        """Create a registry pre-populated with the built-in handlers."""
        registry = cls()
        for operation_type, handler in cls._default_entries().items():
            registry.register_handler(operation_type, handler)
        return registry

    def register_handler(self, operation_type: str, handler: Any) -> None:
        """Register an operation handler."""
        self._handlers[operation_type] = handler

    async def execute_operation(
        self,
        operation: EntityOperation,
        provider: DatabaseProviderProtocol,
    ) -> None:
        """Execute an operation using the registered handler."""
        handler = self._handlers.get(operation.operation_type)
        if not handler:
            raise ValueError(f"Unknown operation type: {operation.operation_type}")
        await handler.execute(operation, provider)


# ---------------------------------------------------------------------------
# Table naming strategy registry
# ---------------------------------------------------------------------------


class SnakeCaseNamingHandler:
    """Handler for snake_case table naming strategy."""

    def get_table_name(self, class_name: str) -> str:
        """Convert PascalCase to snake_case."""
        return re.sub(r"(?<-n)(?=[A-Z])", "_", class_name).lower()


class PluralNamingHandler:
    """Handler for plural table naming strategy."""

    def get_table_name(self, class_name: str) -> str:
        """Pluralise a class name."""
        if class_name.endswith("y"):
            table_name = class_name[:-1] + "ies"
        elif class_name.endswith(("s", "sh", "ch", "x", "z")):
            table_name = class_name + "es"
        else:
            table_name = class_name + "s"
        return table_name.lower()


class LowercaseNamingHandler:
    """Handler for lowercase table naming strategy."""

    def get_table_name(self, class_name: str) -> str:
        """Lowercase the class name."""
        return class_name.lower()


class TableNamingStrategyRegistry:
    """Registry for table naming strategy handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, Any] = {}

    @classmethod
    def _default_entries(cls) -> dict[str, Any]:
        """Declare the built-in table naming strategy handlers."""
        return {
            "snake_case": SnakeCaseNamingHandler(),
            "plural": PluralNamingHandler(),
            "lower": LowercaseNamingHandler(),
        }

    @classmethod
    def with_defaults(cls) -> TableNamingStrategyRegistry:
        """Create a registry pre-populated with the built-in handlers."""
        registry = cls()
        for strategy, handler in cls._default_entries().items():
            registry.register_handler(strategy, handler)
        return registry

    def register_handler(self, strategy: str, handler: Any) -> None:
        """Register a table naming strategy handler."""
        self._handlers[strategy] = handler

    def get_table_name(self, strategy: str, class_name: str) -> str:
        """Return the table name for *class_name* using *strategy*."""
        if callable(strategy):
            return cast("str", strategy(class_name))
        handler = self._handlers.get(strategy)
        if handler:
            return cast("str", handler.get_table_name(class_name))
        return class_name.lower()


# Module-level registries
_table_naming_registry = TableNamingStrategyRegistry.with_defaults()
_operation_handler_registry = OperationHandlerRegistry.with_defaults()

# Re-export from utils for internal use
_entity_to_dict = entity_to_dict


# ---------------------------------------------------------------------------
# SimpleUnitOfWork
# ---------------------------------------------------------------------------
