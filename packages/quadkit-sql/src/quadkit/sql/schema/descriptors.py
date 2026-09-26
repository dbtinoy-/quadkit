"""Index, constraint, and relationship descriptors for the schema model system.

Consumed by :class:`~quadkit.sql.schema.model.Model` via the
``__indexes__`` and ``__constraints__`` class attributes and relationship
class attributes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Index:
    """Database index descriptor."""

    name: str
    columns: str | list[str] = ""
    unique: bool = False
    condition: str | None = None  # Partial index WHERE clause

    def __post_init__(self) -> None:
        if isinstance(self.columns, str):
            self.columns = [self.columns]

    def to_sql(self, table: str, dialect: str = "postgresql") -> str:
        """Render the CREATE INDEX statement for this index."""
        unique = "UNIQUE " if self.unique else ""
        cols = ", ".join(self.columns)
        sql = f"CREATE {unique}INDEX {self.name} ON {table} ({cols})"
        if self.condition:
            sql += f" WHERE {self.condition}"
        return sql


@dataclass
class Constraint:
    """Database constraint descriptor."""

    name: str
    expression: str
    type: str = "CHECK"  # CHECK, UNIQUE, FOREIGN KEY

    def to_sql(self) -> str:
        """Render the CONSTRAINT clause for this constraint."""
        return f"CONSTRAINT {self.name} {self.type} ({self.expression})"


@dataclass
class HasMany:
    """One-to-many relationship descriptor."""

    target: str  # Target model/repository name
    foreign_key: str
    local_key: str = "id"


@dataclass
class BelongsTo:
    """Many-to-one relationship descriptor."""

    target: str
    foreign_key: str
    owner_key: str = "id"


@dataclass
class ManyToMany:
    """Many-to-many relationship via pivot table."""

    target: str
    pivot_table: str
    foreign_key: str
    related_key: str
