"""Scalar-coercion helpers for domain models.

Hosts the implementation of ``DomainModel.model_validate`` (extracted from
:mod:`quadkit.domain.models.base`). The annotation resolver it relies on lives
in :mod:`quadkit.primitives.typing` and is re-exported here for the call sites
that have always imported it from this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from quadkit.primitives.typing import resolve_type_hints as resolve_type_hints

__all__ = ["coerce_and_build", "resolve_type_hints"]


def _extract_attributes(cls: type[Any], data: Any) -> dict[str, Any]:
    """Extract declared fields (and aliases) from an ORM or attribute object."""
    fields = getattr(cls, "__dataclass_fields__", {})
    obj_vars = vars(data) if hasattr(data, "__dict__") else {}
    raw_dict: dict[str, Any] = {}

    for fname, f in fields.items():
        meta = getattr(f, "metadata", {}) or {}
        alias = meta.get("alias")
        if fname in obj_vars:
            raw_dict[fname] = obj_vars[fname]
        elif hasattr(data, fname):
            attr_val = getattr(data, fname)
            # Guard against SQLAlchemy DeclarativeBase.metadata class attribute
            if (
                fname == "metadata"
                and attr_val is not None
                and not isinstance(attr_val, Mapping)
            ):
                continue
            raw_dict[fname] = attr_val
        elif isinstance(alias, str) and hasattr(data, alias):
            raw_dict[alias] = getattr(data, alias)

    before_validators = (getattr(cls, "_model_validators", None) or {}).get(
        "before", []
    )
    if before_validators and obj_vars:
        # Expose raw ORM column attributes to mode="before" model validators,
        # then prune unmapped ORM columns unless extra="allow" is configured.
        candidate = {
            k: v
            for k, v in obj_vars.items()
            if not k.startswith("_") and k not in raw_dict
        }
        candidate.update(raw_dict)
        for validator_fn in before_validators:
            res = validator_fn(cls, candidate)
            if isinstance(res, dict):
                candidate = res

        cfg = getattr(cls, "model_config", None)
        extra_mode = (
            cfg.get("extra")
            if isinstance(cfg, Mapping)
            else getattr(cfg, "extra", None)
        )
        if extra_mode == "allow":
            return candidate

        allowed_keys: set[str] = set(fields.keys())
        for f in fields.values():
            meta = getattr(f, "metadata", {}) or {}
            if isinstance(meta.get("alias"), str):
                allowed_keys.add(meta["alias"])
            for cand_alias in meta.get("aliases", ()):
                allowed_keys.add(str(cand_alias))
        return {k: v for k, v in candidate.items() if k in allowed_keys}

    return raw_dict


def coerce_and_build(
    cls: type[Any],
    data: Any,
    *,
    from_attributes: bool | None = None,
) -> Any:
    """Build *cls* from *data* through the same guard as direct construction."""
    import dataclasses as _dc

    if isinstance(data, cls):
        return data

    raw_dict: dict[str, Any]
    if isinstance(data, Mapping):
        raw_dict = dict(data)
    else:
        cfg = getattr(cls, "model_config", None)
        cfg_from_attrs = (
            cfg.get("from_attributes", False)
            if isinstance(cfg, Mapping)
            else bool(getattr(cfg, "from_attributes", False))
        )
        allow_attrs = (
            cfg_from_attrs if from_attributes is None else bool(from_attributes)
        )
        if not allow_attrs:
            from quadkit.contracts.exceptions.domain import ValidationError

            raise ValidationError(
                f"Input should be a dictionary or mapping, got {type(data).__name__}"
            )
        raw_dict = _extract_attributes(cls, data)

    if not _dc.is_dataclass(cls):
        return cls(**raw_dict)

    from quadkit.domain.models.base import DomainModel

    instance = cls.__new__(cls)
    DomainModel.__init__(cast("DomainModel", instance), **raw_dict)
    return instance
