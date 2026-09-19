"""Dynamic model creation utilities."""

from __future__ import annotations

import dataclasses
from typing import Any

from quadkit.domain.models.base import DomainModel
from quadkit.logging import get_logger

logger = get_logger(__name__)


def _is_dataclass_base(base: type[Any] | tuple[type[Any], ...]) -> bool:
    """Return True if every base in *base* is a stdlib dataclass or DomainModel."""
    bases = base if isinstance(base, tuple) else (base,)
    return all(dataclasses.is_dataclass(b) or issubclass(b, DomainModel) for b in bases)


def _make_dc_fields(
    fields: dict[str, Any],
) -> list[tuple[str, type[Any]] | tuple[str, type[Any], dataclasses.Field[Any]]]:
    """Convert ``name=(type, default)`` field specs to ``make_dataclass`` tuples.

    A default of ``...`` (Ellipsis) means the field is required (no default).
    """
    result: list[
        tuple[str, type[Any]] | tuple[str, type[Any], dataclasses.Field[Any]]
    ] = []
    for name, spec in fields.items():
        if not isinstance(spec, tuple) or len(spec) != 2:  # noqa: PLR2004
            raise TypeError(
                f"Field '{name}' must be a 2-tuple of (type, default). "
                f"Use Ellipsis (...) as the default for required fields."
            )
        field_type, default = spec
        if default is ...:
            # Required field — no default
            result.append((name, field_type))
        elif callable(default) and not isinstance(default, type):
            # Looks like a factory
            result.append(
                (name, field_type, dataclasses.field(default_factory=default))
            )
        else:
            result.append((name, field_type, dataclasses.field(default=default)))
    return result


def create_model(
    model_name: str,
    __base__: type[Any] | tuple[type[Any], ...] | None = None,
    **fields: Any,
) -> type[Any]:
    """Dynamically create a domain model class backed by ``DomainModel``.

    ``DomainModel`` is a stdlib ``@dataclass`` mixin — it is **not** a Pydantic
    ``BaseModel`` subclass and therefore cannot be passed to
    ``pydantic.create_model`` as ``__base__``.  This function uses
    ``dataclasses.make_dataclass`` to build the class correctly so that
    ``DomainModel``'s ``__init__`` (which hard-checks for
    ``__dataclass_fields__``) works without error.

    When *__base__* is a genuine ``pydantic.BaseModel`` subclass (i.e. the
    caller explicitly opted into Pydantic), ``pydantic.create_model`` is used
    instead and ``DomainModel`` is **not** injected.

    Args:
        model_name: The name of the new model class.
        __base__: The base class(es) for the new model. Defaults to
            ``DomainModel``.  Pass a ``pydantic.BaseModel`` subclass to get a
            pure Pydantic model instead.
        **fields: Field definitions as ``name=(type, default)``.  Use
            ``Ellipsis`` (``...``) as the default for required fields.

    Returns:
        A new model class that is either a ``@dataclass`` subclass of
        ``DomainModel`` or a ``pydantic.BaseModel`` subclass.
    """
    resolved_base: type[Any] | tuple[type[Any], ...] = (
        DomainModel if __base__ is None else __base__
    )

    # --- Pydantic BaseModel branch ---
    # If the caller explicitly provided a Pydantic BaseModel base, delegate to
    # pydantic.create_model.  We do NOT inject DomainModel in this path.
    try:
        from pydantic import BaseModel

        bases = resolved_base if isinstance(resolved_base, tuple) else (resolved_base,)
        if any(issubclass(b, BaseModel) for b in bases):
            from pydantic import create_model as _pydantic_create_model

            return _pydantic_create_model(
                model_name,
                __base__=resolved_base,
                **fields,
            )
    except ImportError:
        logger.warning(
            "pydantic_not_installed",
            hint="pip install quadkit",
            detail="pydantic model factory unavailable; using dataclass fallback",
        )

    # --- DomainModel / dataclass branch (canonical path) ---
    # DomainModel is a stdlib @dataclass mixin.  Build the class with
    # dataclasses.make_dataclass so __dataclass_fields__ is populated and
    # DomainModel.__init__ is satisfied.
    if not _is_dataclass_base(resolved_base):
        raise TypeError(
            f"create_model: unsupported base {resolved_base!r}. "
            "Pass a DomainModel subclass or a pydantic.BaseModel subclass."
        )

    dc_fields = _make_dc_fields(fields)
    bases = resolved_base if isinstance(resolved_base, tuple) else (resolved_base,)

    return dataclasses.make_dataclass(
        model_name,
        dc_fields,
        bases=bases,
        init=False,
        eq=False,
    )
