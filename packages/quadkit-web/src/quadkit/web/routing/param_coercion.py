"""Parameter-coercion primitives for request validation.

Low-level helpers used by :mod:`quadkit.web.routing.validation` to build
strict Pydantic models from handler signatures: type-hint resolution,
simple-type detection, model construction, and per-handler model caching.
"""

from __future__ import annotations

from functools import lru_cache
import sys
from typing import Any, get_args, get_origin

from quadkit.domain import DomainModel


def _create_validation_model(model_name: str, **fields: Any) -> type:
    """Create a strict Pydantic validation model (not DomainModel).

    Unlike create_model (which applies @dataclass and bypasses Pydantic's type
    validation), this helper creates a plain pydantic.BaseModel so that type
    coercion errors are raised as pydantic.ValidationError.
    """
    from pydantic import BaseModel, ConfigDict
    from pydantic import create_model as _pm

    class _ValidationBase(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=False)

    return _pm(model_name, __base__=_ValidationBase, **fields)


# 256 entries covers virtually all real-world applications (typical apps have
# well under 100 routes) while avoiding unbounded growth in pathological cases.
@lru_cache(maxsize=256)
def _cached_get_type_hints_for_handler(handler: Any) -> dict[str, Any]:
    from typing import get_type_hints

    # When a handler is wrapped by any decorator using @wraps,
    # __annotations__ are copied but __globals__ points to the wrapper module.
    # With `from __future__ import annotations`, string annotations need the
    # original module's __globals__ to resolve. Follow __wrapped__ chain.
    target = handler
    while hasattr(target, "__wrapped__"):
        target = target.__wrapped__

    globalns = getattr(target, "__globals__", None) or getattr(
        handler, "__globals__", None
    )
    try:
        return get_type_hints(handler, globalns=globalns) or {}
    except (NameError, AttributeError, TypeError):
        pass
    try:
        return get_type_hints(target) or {}
    except (NameError, AttributeError, TypeError):
        pass
    # One unresolvable name — typically ``request: Request`` imported under
    # TYPE_CHECKING in an application module — must not cost every *other*
    # parameter its type: before this, the body DTO beside it was then
    # "assumed DI" and the request failed with a 500. Resolve what can be
    # resolved, one annotation at a time; leave the rest as strings.
    return _resolve_hints_individually(target, globalns)


def _resolve_hints_individually(target: Any, globalns: Any) -> dict[str, Any]:
    import typing

    raw = getattr(target, "__annotations__", None) or {}
    module = sys.modules.get(getattr(target, "__module__", "") or "")
    localns = dict(vars(module)) if module is not None else dict(globalns or {})
    resolved: dict[str, Any] = {}
    for name, annotation in raw.items():
        if not isinstance(annotation, str):
            resolved[name] = annotation
            continue
        try:
            resolved[name] = typing._eval_type(  # type: ignore[attr-defined]
                typing.ForwardRef(annotation), globalns, localns
            )
        except Exception:  # noqa: BLE001 — leave an unresolvable name as the string it was
            resolved[name] = annotation
    return resolved


_SIMPLE_TYPES = {str, int, float, bool}


def _get_cached_query_model(handler: Any) -> type[DomainModel] | None:
    """Get cached query model from handler."""
    cache_target = getattr(handler, "__func__", handler)
    val = getattr(cache_target, "_query_model", None)
    return val if isinstance(val, type) else None


def _set_cached_query_model(handler: Any, model: type[DomainModel] | None) -> None:
    """Set cached query model on handler."""
    cache_target = getattr(handler, "__func__", handler)
    cache_target._query_model = model


def _get_cached_combined_model(handler: Any) -> type[DomainModel] | None:
    """Get cached combined model from handler."""
    cache_target = getattr(handler, "__func__", handler)
    val = getattr(cache_target, "_combined_model", None)
    return val if isinstance(val, type) else None


def _set_cached_combined_model(handler: Any, model: type[DomainModel] | None) -> None:
    """Set cached combined model on handler."""
    cache_target = getattr(handler, "__func__", handler)
    cache_target._combined_model = model


def _is_simple_type(annotation: Any) -> bool:
    """Return True if annotation represents a simple query-deserializable type."""
    if annotation in _SIMPLE_TYPES:
        return True

    import types as _types
    from typing import Union

    origin = get_origin(annotation)
    # Optional[X] / X | None: the union's origin is Union (typing) or
    # UnionType (PEP 604), never type(None) itself.
    if origin in (Union, _types.UnionType):
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1 and non_none[0] in _SIMPLE_TYPES:
            return True

    return False
