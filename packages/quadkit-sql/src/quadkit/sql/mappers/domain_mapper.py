#!/usr/bin/env python3
from __future__ import annotations

# pyright: reportMissingImports=false

"""Data mapper for DomainModel entities (dataclass-based)."""

from collections.abc import Callable
from dataclasses import MISSING
from dataclasses import fields as dataclass_fields
from datetime import date, datetime, time
import types
from typing import Any, Union, get_type_hints
from uuid import UUID

from quadkit.serialization import dumps_str, loads
from quadkit.sql.mappers.base import DataMapper, FieldMapping, MappingError, TEntity


class DomainDataMapper(DataMapper[TEntity, dict[str, Any]]):
    """Data mapper for DomainModel entities."""

    def __init__(
        self,
        entity_type: type[TEntity],
        field_mappings: list[FieldMapping] | None = None,
        auto_map: bool = True,
        column_prefix: str = "",
        column_suffix: str = "",
    ):
        """Initialize the DomainModel data mapper.

        Args:
            entity_type: The DomainModel class to map to/from
            field_mappings: Custom field mappings (optional, auto-generated if None)
            auto_map: Whether to automatically map fields by name
            column_prefix: Prefix to add to column names
            column_suffix: Suffix to add to column names
        """
        if not hasattr(entity_type, "__dataclass_fields__"):
            raise TypeError(
                f"entity_type must be a dataclass, got {entity_type}. "
                "Use DomainModel or any dataclass type.",
            )

        super().__init__(entity_type)
        self.auto_map = auto_map
        self.column_prefix = column_prefix
        self.column_suffix = column_suffix

        self.field_mappings = field_mappings or self._auto_generate_mappings(
            entity_type,
        )

        # Create lookup dictionaries for performance
        self._entity_to_db = {fm.entity_field: fm for fm in self.field_mappings}
        self._db_to_entity = {fm.db_column: fm for fm in self.field_mappings}

    def _auto_generate_mappings(
        self,
        entity_type: type[Any],
    ) -> list[FieldMapping]:
        """Auto-generate field mappings from DomainModel dataclass fields."""
        mappings = []
        type_hints = get_type_hints(entity_type)

        for field in dataclass_fields(entity_type):
            # Skip ClassVar and Private fields
            if field.name.startswith("_") or field.metadata.get("classvar"):
                continue

            # Get field name (use name as-is)
            entity_field = field.name

            # Generate column name
            column_name = self.column_prefix + field.name + self.column_suffix

            # Get the type from type hints
            python_type = type_hints.get(field.name)

            # Create field mapping with type converters
            converter = self._get_type_converter(python_type)
            reverse_converter = self._get_reverse_type_converter(python_type)

            # Determine if field is required (no default)
            required = field.default is MISSING and field.default_factory is MISSING
            default_value = field.default if field.default is not MISSING else None
            if field.default_factory is not MISSING:
                default_value = field.default_factory

            mapping = FieldMapping(
                entity_field=entity_field,
                db_column=column_name,
                converter=converter,
                reverse_converter=reverse_converter,
                required=required,
                default_value=default_value,
            )
            mappings.append(mapping)

        return mappings

    @staticmethod
    def _unwrap_optional(field_type: Any) -> Any:
        """Unwrap Optional/Union types to get the inner non-None type.

        Handles both typing.Union (Optional[T]) and types.UnionType (T | None)
        from Python 3.10+ new-style union syntax.
        """
        # Handle types.UnionType (Python 3.10+ X | None syntax)
        if isinstance(field_type, types.UnionType):
            args = field_type.__args__
            if len(args) == 2 and type(None) in args:
                return args[0] if args[1] is type(None) else args[1]

        # Handle typing.Union (Optional[T])
        if hasattr(field_type, "__origin__") and field_type.__origin__ is Union:
            args = field_type.__args__
            if len(args) == 2 and type(None) in args:
                return args[0] if args[1] is type(None) else args[1]

        return field_type

    def _get_type_converter(self, field_type: Any) -> Callable[[Any], Any] | None:
        """Get converter function for converting DB value to entity value."""
        if field_type is None:
            return None

        # Handle Optional types (typing.Union and types.UnionType)
        field_type = self._unwrap_optional(field_type)

        # Handle generic types (List[T], Dict[K, V], etc.)
        origin = getattr(field_type, "__origin__", None)
        if origin is not None:
            field_type = origin

        # Type-specific converters
        converters: dict[Any, Callable[[Any], Any]] = {
            datetime: self._parse_datetime,
            date: self._parse_date,
            time: self._parse_time,
            UUID: lambda x: UUID(x) if isinstance(x, str) else x,
            dict: lambda x: loads(x) if isinstance(x, str) else x,
            list: lambda x: loads(x) if isinstance(x, str) else x,
        }

        return converters.get(field_type)

    def _get_reverse_type_converter(
        self,
        field_type: Any,
    ) -> Callable[[Any], Any] | None:
        """Get converter function for converting entity value to DB value."""
        if field_type is None:
            return None

        # Handle Optional types (typing.Union and types.UnionType)
        field_type = self._unwrap_optional(field_type)

        # Handle generic types (List[T], Dict[K, V], etc.)
        origin = getattr(field_type, "__origin__", None)
        if origin is not None:
            field_type = origin

        # Type-specific reverse converters
        converters: dict[Any, Callable[[Any], Any]] = {
            datetime: lambda x: x.isoformat() if x else None,
            date: lambda x: x.isoformat() if x else None,
            time: lambda x: x.isoformat() if x else None,
            UUID: str,
            dict: dumps_str,
            list: dumps_str,
        }

        return converters.get(field_type)

    def _parse_datetime(self, value: Any) -> datetime | None:
        """Parse datetime from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            # Try ISO format first
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        raise ValueError(f"Cannot parse datetime from {value}")

    def _parse_date(self, value: Any) -> date | None:
        """Parse date from various formats."""
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        raise ValueError(f"Cannot parse date from {value}")

    def _parse_time(self, value: Any) -> time | None:
        """Parse time from various formats."""
        if value is None:
            return None
        if isinstance(value, time):
            return value
        if isinstance(value, str):
            return time.fromisoformat(value)
        raise ValueError(f"Cannot parse time from {value}")

    def to_entity(self, row: dict[str, Any]) -> TEntity:
        """Convert a database row to a DomainModel entity.

        Args:
            row: Database row as a dictionary

        Returns:
            DomainModel instance

        Raises:
            MappingError: If the row cannot be mapped to an entity
        """
        self.validate_row(row)

        entity_data = {}

        # Map fields using field mappings
        for mapping in self.field_mappings:
            db_value = row.get(mapping.db_column)

            if db_value is None:
                if mapping.required and mapping.default_value is None:
                    raise MappingError(
                        f"Required field '{mapping.entity_field}' is missing from row",
                        entity_type=self.entity_type.__name__,
                        field_name=mapping.entity_field,
                    )
                entity_data[mapping.entity_field] = mapping.default_value
            else:
                try:
                    converted_value = mapping.convert_to_entity(db_value)
                    entity_data[mapping.entity_field] = converted_value
                except (ValueError, TypeError, AttributeError) as e:
                    raise MappingError(
                        f"Failed to convert field '{mapping.entity_field}': {e}",
                        entity_type=self.entity_type.__name__,
                        field_name=mapping.entity_field,
                        value=db_value,
                    ) from e

        # Create entity instance directly with field names
        try:
            return self.entity_type(**entity_data)
        except (ValueError, TypeError, AttributeError) as e:
            raise MappingError(
                f"Failed to create entity: {e}",
                entity_type=self.entity_type.__name__,
            ) from e

    def to_row(self, entity: TEntity) -> dict[str, Any]:
        """Convert a DomainModel entity to a database row.

        Args:
            entity: DomainModel instance

        Returns:
            Database row as a dictionary

        Raises:
            MappingError: If the entity cannot be converted to a row
        """
        self.validate_entity(entity)

        row_data = {}

        # Convert entity to dict using dataclass approach
        entity_dict: dict[str, Any] = {}
        for f in dataclass_fields(entity):  # type: ignore[arg-type]
            value = getattr(entity, f.name, None)
            entity_dict[f.name] = value

        # Map fields using field mappings
        for mapping in self.field_mappings:
            entity_value = entity_dict.get(mapping.entity_field)

            if entity_value is None:
                if mapping.required:
                    raise MappingError(
                        f"Required field '{mapping.entity_field}' is None in entity",
                        entity_type=self.entity_type.__name__,
                        field_name=mapping.entity_field,
                    )
                continue

            try:
                row_data[mapping.db_column] = mapping.convert_to_db(entity_value)
            except (ValueError, TypeError, AttributeError) as e:
                raise MappingError(
                    f"Failed to convert field '{mapping.entity_field}' to DB value: {e}",
                    entity_type=self.entity_type.__name__,
                    field_name=mapping.entity_field,
                    value=entity_value,
                ) from e

        # Add unmapped fields if auto_map is enabled
        if self.auto_map:
            row_data.update(
                {
                    field_name: field_value
                    for field_name, field_value in entity_dict.items()
                    if field_name not in self._entity_to_db
                },
            )

        # Normalize datetime/date/time values to ISO strings for DB storage
        for k, v in list(row_data.items()):
            if isinstance(v, date | datetime | time):
                row_data[k] = v.isoformat()

        return row_data
