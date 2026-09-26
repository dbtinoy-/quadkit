"""Domain model analysis for migration generation."""

from __future__ import annotations

from dataclasses import MISSING
from dataclasses import Field as DataclassField
from datetime import datetime
import inspect
import re
from typing import Any, Union

from quadkit.domain import DomainModel
from quadkit.sql.migrations.base import MigrationError
from quadkit.sql.types import ColumnDefinition, TableDefinition


class _ResolvedField:
    """Read-only dataclass-field view with a resolved type annotation.

    ``dataclasses.Field`` objects are immutable and not dataclass
    instances (``dataclasses.replace`` is unavailable), so stringified
    annotations are resolved by wrapping the original field and exposing
    the same attributes ``_analyze_field`` reads (``.type``, ``.default``,
    ``.default_factory``, ``.metadata``).
    """

    def __init__(self, inner: DataclassField, type_: Any) -> None:
        self._inner = inner
        self.type = type_

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def default(self) -> Any:
        return self._inner.default

    @property
    def default_factory(self) -> Any:
        return self._inner.default_factory

    @property
    def metadata(self) -> Any:
        return self._inner.metadata


def replace_field_type(field_info: DataclassField, type_: Any) -> _ResolvedField:
    """Wrap *field_info* exposing a resolved (non-string) ``type``."""
    return _ResolvedField(field_info, type_)


class ModelAnalyzer:
    """Analyzes Domain models to generate database schema definitions"""

    # Mapping of Python types to SQL types
    TYPE_MAPPING = {
        str: "VARCHAR",
        int: "INTEGER",
        float: "FLOAT",
        bool: "BOOLEAN",
        datetime: "TIMESTAMP",
        bytes: "BYTEA",
        # Add more mappings as needed
    }

    def analyze_model(
        self,
        model: type[DomainModel],
        table_name: str | None = None,
    ) -> TableDefinition:
        """Analyze a Domain model and return table definition"""
        if not issubclass(model, DomainModel):
            raise MigrationError(f"Model {model} must inherit from DomainModel")

        # Get table name from model or parameter
        table_name = table_name or self._get_table_name(model)

        # Analyze fields using dataclass fields API
        columns = []
        from dataclasses import fields as dataclass_fields
        from typing import get_type_hints

        # Resolve stringified annotations (PEP 563 / forward refs) to real
        # types; without this, models defined under
        # ``from __future__ import annotations`` would silently degrade
        # every column to VARCHAR.  Unresolvable references fall back to
        # the raw annotation (→ VARCHAR default in _analyze_field).
        try:
            hints = get_type_hints(model)
        except Exception:  # noqa: BLE001 — keep the raw annotation on failure
            hints = {}

        for f in dataclass_fields(model):  # type: ignore[arg-type]
            # Convert field name to snake_case for database column
            column_name = self._camel_to_snake(f.name)
            resolved = hints.get(f.name)
            if isinstance(f.type, str) and resolved is not None:
                # Rebind the raw field descriptor with the resolved type.
                # (Field objects are immutable; _analyze_field only reads
                # .type/.default/.default_factory/.metadata.)
                f = replace_field_type(f, resolved)  # type: ignore[assignment]
            column = self._analyze_field(column_name, f)
            columns.append(column)

        # Create table definition
        table_def = TableDefinition(name=table_name, columns=columns)

        # Add indexes and constraints based on field annotations
        self._add_indexes_and_constraints(table_def, model)

        return table_def

    def _get_table_name(self, model: type[DomainModel]) -> str:
        """Get table name from model"""
        # Check for table name in model metadata
        if hasattr(model, "Meta") and hasattr(model.Meta, "table_name"):
            return str(model.Meta.table_name)

        # Default to snake_case model name
        return self._camel_to_snake(model.__name__)

    def _camel_to_snake(self, name: str) -> str:
        """Convert CamelCase to snake_case"""

        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    def _analyze_field(
        self,
        field_name: str,
        field_info: DataclassField,
    ) -> ColumnDefinition:
        """Analyze a single field and return column definition"""
        # Get Python type
        python_type = field_info.type

        # Handle Optional types
        nullable = False
        if self._is_optional_type(python_type):
            nullable = True
            python_type = self._get_optional_inner_type(python_type)

        foreign_key: str | None = None
        # Handle List types (for foreign keys or arrays)
        if self._is_list_type(python_type):
            # This could be a foreign key relationship or array type
            inner_type = self._get_list_inner_type(python_type)
            if inspect.isclass(inner_type) and issubclass(inner_type, DomainModel):
                # Foreign key relationship
                foreign_table = self._get_table_name(inner_type)
                foreign_key = f"{foreign_table}.id"
                column_type = "INTEGER"  # Assuming ID is integer
            else:
                # Array type
                column_type = self._get_sql_type(inner_type) + "[]"
        else:
            column_type = self._get_sql_type(python_type)

        # Get field constraints from dataclass
        default_value = None
        if field_info.default is not MISSING:
            default_value = self._format_default_value(field_info.default)

        # Get extra metadata from field metadata (MappingProxyType from dataclasses)
        extra = field_info.metadata

        # Check for primary key
        primary_key = bool(extra.get("primary_key", False)) or field_name == "id"

        # Check for unique constraint
        unique = bool(extra.get("unique", False))

        # Check for index
        index = bool(extra.get("index", False))

        # Check for foreign key (metadata overrides auto-detected value)
        fk_raw = extra.get("foreign_key")
        if fk_raw is not None:
            foreign_key = str(fk_raw)

        # Get comment
        description = extra.get("description", "")

        return ColumnDefinition(
            name=field_name,
            type_sql=column_type,
            nullable=nullable,
            default=default_value,
            primary_key=primary_key,
            unique=unique,
            index=index,
            foreign_key=foreign_key,
            comment=description,
        )

    def _is_optional_type(self, type_hint: Any) -> bool:
        """Check if type is Optional (supports PEP 604 unions and typing.Union)."""
        # Handle typing.Union (has __origin__ and __args__)
        if hasattr(type_hint, "__origin__") and type_hint.__origin__ is Union:
            return type(None) in getattr(type_hint, "__args__", ())

        # Handle PEP 604 (X | Y) which may expose __args__ without __origin__
        args = getattr(type_hint, "__args__", None)
        if args is not None:
            return type(None) in args

        return False

    def _get_optional_inner_type(self, type_hint: Any) -> Any:
        """Get the inner type from Optional[T]"""
        return next(arg for arg in type_hint.__args__ if arg is not type(None))

    def _is_list_type(self, type_hint: Any) -> bool:
        """Check if type is List"""
        if hasattr(type_hint, "__origin__"):
            return type_hint.__origin__ is list
        return False

    def _get_list_inner_type(self, type_hint: Any) -> Any:
        """Get the inner type from List[T]"""
        return type_hint.__args__[0]

    def _get_sql_type(self, python_type: Any) -> str:
        """Convert Python type to SQL type"""
        # Handle direct type mappings
        if python_type in self.TYPE_MAPPING:
            return self.TYPE_MAPPING[python_type]

        # Handle string annotations
        if isinstance(python_type, str):
            # This is a forward reference, return VARCHAR as default
            return "VARCHAR"

        # Handle classes that might be enums or custom types
        if inspect.isclass(python_type):
            if issubclass(python_type, str):
                return "VARCHAR"
            if issubclass(python_type, int):
                return "INTEGER"
            if hasattr(python_type, "__members__"):  # Enum
                return "VARCHAR"  # Store enum as string

        # Default to VARCHAR for unknown types
        return "VARCHAR"

    def _format_default_value(self, value: Any) -> str:
        """Format default value for SQL"""
        if isinstance(value, str):
            return f"'{value}'"
        if isinstance(value, bool):
            return str(value).upper()
        if isinstance(value, (int, float)):
            return str(value)
        if value is None:
            return "NULL"
        return str(value)

    def _add_indexes_and_constraints(
        self,
        table_def: TableDefinition,
        model: type[DomainModel],
    ) -> None:
        """Add indexes and constraints based on model metadata"""
        # Check for model-level metadata
        if hasattr(model, "Meta"):
            meta = model.Meta

            # Add table indexes
            if hasattr(meta, "indexes"):
                table_def.indexes.extend(meta.indexes)

            # Add table constraints
            if hasattr(meta, "constraints"):
                table_def.constraints.extend(meta.constraints)
