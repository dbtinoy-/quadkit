"""Scalar-coercion helpers for domain models.

Hosts the implementation of ``DomainModel.model_validate`` (extracted from
:mod:`quadkit.domain.models.base`) together with the defensive type-hint
resolution used at class-creation time.
"""

from __future__ import annotations

from typing import Any, Union, get_args, get_origin, get_type_hints


def resolve_type_hints(cls: type) -> dict[str, Any]:
    """Resolve type hints for a class, falling back to typing-augmented namespaces.

    When ``from __future__ import annotations`` is used, annotations are strings
    that ``get_type_hints()`` must evaluate. Some classes reference symbols like
    ``ClassVar`` or ``Any`` that aren't in the class module's global namespace.
    This helper retries with typing symbols injected.

    Args:
        cls: The class to resolve type hints for.

    Returns:
        A dict mapping field names to their resolved types. Empty dict on failure.
    """
    import sys
    import typing

    try:
        return get_type_hints(cls)
    except (NameError, AttributeError, TypeError):
        pass

    # Retry with typing symbols + class module globals
    try:
        module = sys.modules.get(cls.__module__)
        module_ns = dict(vars(module)) if module else {}
        typing_ns = {name: getattr(typing, name) for name in dir(typing)}
        globalns = {**typing_ns, **module_ns}
        return get_type_hints(cls, globalns=globalns)
    except (NameError, AttributeError, TypeError):
        pass

    return {}


def coerce_and_build(cls: type[Any], data: dict[str, Any]) -> Any:
    """Coerce scalar fields in *data* and build an instance of *cls*.

    Extracted body of ``DomainModel.model_validate``; construction always
    goes through ``cls(**...)`` so subclass hooks keep running.

    Args:
        cls: The domain model class being validated.
        data: Raw field values (e.g. from JSON or env sources).

    Returns:
        A new instance of *cls*.

    Raises:
        ValueError: If a scalar value cannot be coerced to its annotated type.
    """
    import dataclasses as _dc

    # Evaluate once: repeating an identical call after its early-return
    # guard trips mypy's unreachable-statement analysis under
    # --warn-unreachable.
    is_dc = _dc.is_dataclass(cls)
    if not is_dc:
        return cls(**data)

    # getattr returns Any so the except below stays reachable: static
    # narrowing assumes get_type_hints cannot raise, but forward refs
    # raise NameError at runtime.
    hints_cache: Any = getattr(cls, "_cached_type_hints", None)
    try:
        hints = hints_cache or get_type_hints(cls)
    except (NameError, TypeError, ValueError):
        return cls(**data)

    coerced: dict[str, Any] = {}
    for key, value in data.items():
        expected = hints.get(key)
        if expected is None:
            coerced[key] = value
            continue

        origin = get_origin(expected)
        if origin is Union:
            args = get_args(expected)
            non_none = [a for a in args if a is not type(None)]
            if value is None:
                coerced[key] = None
                continue
            if len(non_none) == 1:
                expected = non_none[0]
                origin = get_origin(expected)

        if (
            origin is None
            and isinstance(expected, type)
            and expected in (int, float, str, bool)
            and not isinstance(value, expected)
        ):
            if expected is bool:
                if isinstance(value, str):
                    coerced[key] = value.lower() not in ("false", "0", "")
                else:
                    coerced[key] = bool(value)
            else:
                try:
                    coerced[key] = expected(value)
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"Field '{key}': cannot coerce {value!r} to {expected.__name__}"
                    ) from exc
        else:
            # SecretStr coercion from plain string (env vars, JSON)
            _SecretStr: Any
            try:
                from quadkit.validation import SecretStr as _SecretStrMod

                _SecretStr = _SecretStrMod
            except ImportError:
                _SecretStr = None

            if (
                _SecretStr is not None
                and expected is _SecretStr
                and isinstance(value, str)
                and not isinstance(value, _SecretStr)
            ):
                coerced[key] = _SecretStr(value)
            else:
                coerced[key] = value

    return cls(**coerced)
