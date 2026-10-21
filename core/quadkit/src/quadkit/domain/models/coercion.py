"""Scalar-coercion helpers for domain models.

Hosts the implementation of ``DomainModel.model_validate`` (extracted from
:mod:`quadkit.domain.models.base`). The annotation resolver it relies on lives
in :mod:`quadkit.primitives.typing` and is re-exported here for the call sites
that have always imported it from this module.
"""

from __future__ import annotations

from typing import Any, cast

# The annotation resolver lives in `quadkit.primitives.typing` because it is not
# a domain concern: `quadkit.mapping` needs the same answer ("what types does
# this model declare") to match a source object's fields against a dataclass
# destination, and two resolvers would eventually disagree.
from quadkit.primitives.typing import resolve_type_hints as resolve_type_hints

__all__ = ["coerce_and_build", "resolve_type_hints"]


def coerce_and_build(cls: type[Any], data: dict[str, Any]) -> Any:
    """Build *cls* from *data* through the same guard as direct construction.

    ``model_validate`` — the hydration path ``GenericRepository`` and every
    ``from_dict``-shaped caller goes through — used to run a narrow coercion
    table of its own (int/float/str/bool) and then ``cls(**coerced)``. On a
    plain ``@dataclass`` subclass that bypasses everything ``DomainModel``
    promises:

    * a row's ISO timestamp stayed a ``str``, because ``datetime`` was never in
      the table;
    * an unknown column raised a bare ``TypeError: unexpected keyword
      argument`` instead of landing in ``model_extra``;
    * ``Field(...)`` constraints and the field/model validators never ran, so a
      ``Field(min_length=...)`` declaration was documentation, not a check.

    Delegating to ``DomainModel.__init__`` — the path a directly constructed
    model already takes — fixes all three by deleting the second
    implementation rather than extending it. One guard, one behaviour:
    ``Model.model_validate(row)`` and ``Model(**row)`` now agree.

    Args:
        cls: The domain model class being validated.
        data: Raw field values (e.g. a database row or a decoded JSON body).

    Returns:
        A new instance of *cls*.

    Raises:
        ValidationError: If required fields are missing or a declared
            constraint or field validator rejects a value.
    """
    import dataclasses as _dc

    if not _dc.is_dataclass(cls):
        return cls(**data)

    # Imported here: ``base`` imports this module at class-creation time.
    from quadkit.domain.models.base import DomainModel

    instance = cls.__new__(cls)
    # ``cls`` is only known to be a dataclass here, so the freshly allocated
    # instance has to be named as the ``DomainModel`` it is about to be
    # initialised as before its ``__init__`` can be called directly.
    DomainModel.__init__(cast("DomainModel", instance), **data)
    return instance
