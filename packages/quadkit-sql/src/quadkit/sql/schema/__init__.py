"""Declarative schema model system for quadkit-sql.

Provides Model base class, Field descriptors, relationships,
indexes, constraints, and lifecycle hooks.
"""

from __future__ import annotations

from quadkit.sql.schema.model import (
    BelongsTo,
    Constraint,
    Field,
    FieldType,
    HasMany,
    Index,
    ManyToMany,
    Model,
    ModelMeta,
    after_create,
    after_delete,
    after_update,
    before_create,
    before_delete,
    before_update,
    fire_hooks,
)

__all__ = [
    "BelongsTo",
    "Constraint",
    "Field",
    "FieldType",
    "HasMany",
    "Index",
    "ManyToMany",
    "Model",
    "ModelMeta",
    "after_create",
    "after_delete",
    "after_update",
    "before_create",
    "before_delete",
    "before_update",
    "fire_hooks",
]
