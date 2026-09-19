"""Pydantic field definitions and validators — re-exported from Pydantic.

All consumers import from ``quadkit.validation`` as before; this module
is now a thin re-export layer with zero breaking changes.

``field_validator`` and ``model_validator`` are thin wrappers that set the
custom introspection attributes (``_field_validator``, ``_validator_mode``,
``_validator_fields``) expected by ``DomainModel``'s validator dispatch while
remaining compatible with ``@classmethod``-decorated methods.

``ValidationError`` is **not** defined here — import it from
``quadkit.contracts.exceptions.domain`` which is the single canonical
definition that inherits from ``QuadkitError``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ConfigDict as ConfigDict
from pydantic import EmailStr as EmailStr
from pydantic import Field as Field
from pydantic import HttpUrl as HttpUrl
from pydantic import SecretStr as SecretStr

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "ConfigDict",
    "EmailStr",
    "Field",
    "HttpUrl",
    "SecretStr",
    "field_validator",
    "model_validator",
]


def field_validator(
    *fields: str,
    mode: str = "after",
    **kwargs: Any,
) -> Callable[[Any], Any]:
    """Mark a method as a field validator for DomainModel validator dispatch.

    Applies custom introspection attributes (``_field_validator``,
    ``_validator_mode``, ``_validator_fields``) so that
    ``collect_field_validators`` can discover the validator.  Compatible with
    both plain functions and ``@classmethod``-decorated methods — apply
    ``@classmethod`` *below* this decorator when needed.

    Args:
        *fields: Field names this validator applies to.
        mode: ``"before"`` or ``"after"`` (default ``"after"``).
        **kwargs: Ignored; accepted for API compatibility.

    Returns:
        A decorator that annotates the method with validator metadata.
    """

    def decorator(func: Any) -> Any:
        underlying: Any = func.__func__ if isinstance(func, classmethod) else func
        underlying._field_validator = True
        underlying._validator_mode = mode
        underlying._validator_fields = fields
        return func

    return decorator


def model_validator(
    *,
    mode: str = "wrap",
    **kwargs: Any,
) -> Callable[[Any], Any]:
    """Mark a method as a model validator for DomainModel validator dispatch.

    Applies custom introspection attributes (``_model_validator``,
    ``_validator_mode``) so that ``collect_model_validators`` can discover the
    validator.  Compatible with both plain functions and ``@classmethod``-
    decorated methods — apply ``@classmethod`` *below* this decorator when
    needed.

    Args:
        mode: ``"before"``, ``"after"``, or ``"wrap"`` (default ``"wrap"``).
        **kwargs: Ignored; accepted for API compatibility.

    Returns:
        A decorator that annotates the method with validator metadata.
    """

    def decorator(func: Any) -> Any:
        underlying: Any = func.__func__ if isinstance(func, classmethod) else func
        underlying._model_validator = True
        underlying._validator_mode = mode
        return func

    return decorator
