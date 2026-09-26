"""
SpecificationProtocol pattern for Quadkit DB.

Two variants:

- ``specification.memory`` — In-memory predicate specs (``is_satisfied_by(entity)``)
- ``specification.sql`` — SQL-generating specs (``to_sql(dialect)``)

Repositories use the SQL variant.
"""

from __future__ import annotations

from quadkit.sql.specification.memory import (
    AndMemorySpecification,
    BoolSpecification,
    CompositeMemorySpecification,
    CustomSpecification,
    IntSpecification,
    MemorySpecification,
    MemorySpecificationBuilder,
    NotMemorySpecification,
    OrMemorySpecification,
    StringSpecification,
    matches,
)
from quadkit.sql.specification.memory import (
    FieldSpecification as MemoryFieldSpecification,
)
from quadkit.sql.specification.memory import (
    and_specs as and_memory_specs,
)
from quadkit.sql.specification.memory import (
    not_spec as not_memory_spec,
)
from quadkit.sql.specification.memory import (
    or_specs as or_memory_specs,
)
from quadkit.sql.specification.sql import (
    AndSqlSpecification,
    FieldBetween,
    FieldEquals,
    FieldGreaterThan,
    FieldIn,
    FieldIsNotNull,
    FieldIsNull,
    FieldLessThan,
    FieldLike,
    NotSqlSpecification,
    OrSqlSpecification,
    RawSpecification,
    SqlSpecification,
)
from quadkit.sql.specification.sql import (
    and_specs as and_sql_specs,
)
from quadkit.sql.specification.sql import (
    not_spec as not_sql_spec,
)
from quadkit.sql.specification.sql import (
    or_specs as or_sql_specs,
)

__all__ = [
    "AndMemorySpecification",
    "AndSqlSpecification",
    "BoolSpecification",
    "CompositeMemorySpecification",
    "CustomSpecification",
    "FieldBetween",
    "FieldEquals",
    "FieldGreaterThan",
    "FieldIn",
    "FieldIsNotNull",
    "FieldIsNull",
    "FieldLessThan",
    "FieldLike",
    "IntSpecification",
    "MemoryFieldSpecification",
    "MemorySpecification",
    "MemorySpecificationBuilder",
    "NotMemorySpecification",
    "NotSqlSpecification",
    "OrMemorySpecification",
    "OrSqlSpecification",
    "RawSpecification",
    "SqlSpecification",
    "StringSpecification",
    "and_memory_specs",
    "and_sql_specs",
    "matches",
    "not_memory_spec",
    "not_sql_spec",
    "or_memory_specs",
    "or_sql_specs",
]
