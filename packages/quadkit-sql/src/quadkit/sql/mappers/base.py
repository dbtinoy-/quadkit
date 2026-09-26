"""Base data mapper for entity mapping."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from quadkit.contracts.exceptions import MappingError as CoreMappingError

TEntity = TypeVar("TEntity")
TRow = TypeVar("TRow")


class MappingError(CoreMappingError):
    """Exception raised when entity mapping fails."""

    _code: str = "QK_ERR_SQL_037"

    def __init__(
        self,
        message: str = "Entity mapping failed",
        entity_type: str | None = None,
        field_name: str | None = None,
        value: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.entity_type = entity_type
        self.field_name = field_name
        self.value = value

    def __str__(self) -> str:
        parts = [self.message]
        if self.entity_type:
            parts.append(f"entity_type={self.entity_type}")
        if self.field_name:
            parts.append(f"field={self.field_name}")
        if self.value is not None:
            parts.append(f"value={self.value}")
        return "MappingError(" + ", ".join(parts) + ")"


class DataMapper(ABC, Generic[TEntity, TRow]):
    """Abstract base class for data mappers that convert between entities and database rows.

    This class provides the foundation for mapping database rows to domain entities
    and vice versa. It supports both single entity mapping and bulk operations.
    """

    def __init__(self, entity_type: type[TEntity]):
        """Initialize the data mapper.

        Args:
            entity_type: The type of entity this mapper handles
        """
        self.entity_type = entity_type

    @abstractmethod
    def to_entity(self, row: TRow) -> TEntity:
        """Convert a database row to an entity.

        Args:
            row: Database row data (dict for SQL, document for MongoDB, etc.)

        Returns:
            The mapped entity instance

        Raises:
            MappingError: If the row cannot be mapped to an entity
        """

    @abstractmethod
    def to_row(self, entity: TEntity) -> TRow:
        """Convert an entity to a database row.

        Args:
            entity: The entity to convert

        Returns:
            Database row data

        Raises:
            MappingError: If the entity cannot be converted to a row
        """

    def to_entities(self, rows: list[TRow]) -> list[TEntity]:
        """Convert multiple database rows to entities.

        Args:
            rows: List of database row data

        Returns:
            List of mapped entity instances

        Raises:
            MappingError: If any row cannot be mapped
        """
        entities = []
        for row in rows:
            try:
                entities.append(self.to_entity(row))
            except MappingError as e:
                raise MappingError(
                    f"Failed to map row at index {len(entities)}: {e.message}",
                    entity_type=e.entity_type,
                    field_name=e.field_name,
                    value=e.value,
                ) from e
        return entities

    def to_rows(self, entities: list[TEntity]) -> list[TRow]:
        """Convert multiple entities to database rows.

        Args:
            entities: List of entities to convert

        Returns:
            List of database row data

        Raises:
            MappingError: If any entity cannot be converted
        """
        rows = []
        for entity in entities:
            try:
                rows.append(self.to_row(entity))
            except MappingError as e:
                raise MappingError(
                    f"Failed to map entity at index {len(rows)}: {e.message}",
                    entity_type=e.entity_type,
                    field_name=e.field_name,
                    value=e.value,
                ) from e
        return rows

    def validate_entity(self, entity: TEntity) -> None:
        """Validate an entity before mapping.

        Args:
            entity: The entity to validate

        Raises:
            MappingError: If the entity is invalid
        """
        if not isinstance(entity, self.entity_type):
            raise MappingError(
                f"Entity must be of type {self.entity_type.__name__}, got {type(entity).__name__}",
                entity_type=self.entity_type.__name__,
            )

    def validate_row(self, row: TRow) -> None:
        """Validate a row before mapping.

        Args:
            row: The row to validate

        Raises:
            MappingError: If the row is invalid
        """
        if row is None:
            raise MappingError(
                "Row cannot be None",
                entity_type=self.entity_type.__name__,
            )


class FieldMapping:
    """Configuration for mapping between entity fields and database columns."""

    def __init__(
        self,
        entity_field: str,
        db_column: str,
        converter: Callable[[Any], Any] | None = None,
        reverse_converter: Callable[[Any], Any] | None = None,
        required: bool = True,
        default_value: Any = None,
    ):
        """Initialize field mapping configuration.

        Args:
            entity_field: Name of the field in the entity
            db_column: Name of the column in the database
            converter: Function to convert from DB value to entity value
            reverse_converter: Function to convert from entity value to DB value
            required: Whether this field is required for mapping
            default_value: Default value if field is missing
        """
        self.entity_field = entity_field
        self.db_column = db_column
        self.converter = converter
        self.reverse_converter = reverse_converter or converter
        self.required = required
        self.default_value = default_value

    def convert_to_entity(self, db_value: Any) -> Any:
        """Convert database value to entity value."""
        if self.converter and db_value is not None:
            return self.converter(db_value)
        return db_value

    def convert_to_db(self, entity_value: Any) -> Any:
        """Convert entity value to database value."""
        if self.reverse_converter and entity_value is not None:
            return self.reverse_converter(entity_value)
        return entity_value
