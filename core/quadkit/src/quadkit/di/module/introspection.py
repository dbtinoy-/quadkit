"""Module introspection helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions.provider import ModuleError
from quadkit.di.module.constants import MODULE_METADATA_ATTR
from quadkit.di.module.dynamic import DynamicModule

if TYPE_CHECKING:
    from quadkit.di.module.metadata import ModuleMetadata


def get_module_metadata(cls: type) -> ModuleMetadata | None:
    """Read :class:`ModuleMetadata` from a class, or ``None`` if not a module.

    Only checks the class's own ``__dict__`` — inherited metadata from
    a parent module is **not** returned.
    """
    return cls.__dict__.get(MODULE_METADATA_ATTR)


def is_module(cls: type) -> bool:
    """Check if a class is a declared Quadkit module.

    Returns ``True`` only if *cls* itself is decorated with ``@module``.
    Inheriting from a decorated parent does NOT make a class a module.
    """
    return isinstance(cls, type) and MODULE_METADATA_ATTR in cls.__dict__


def is_dynamic_module(obj: Any) -> bool:
    """Check if an object is a :class:`DynamicModule` descriptor."""
    return isinstance(obj, DynamicModule)


def get_module_name(cls_or_dynamic: type | DynamicModule) -> str:
    """Get the module name from a class or :class:`DynamicModule`.

    Falls back to the class ``__name__`` if no metadata is found.
    """
    if isinstance(cls_or_dynamic, DynamicModule):
        return cls_or_dynamic.resolved_name
    meta = get_module_metadata(cls_or_dynamic)
    if meta is not None:
        return meta.name
    return cls_or_dynamic.__name__


def get_module_class(entry: type | DynamicModule) -> type:
    """Extract the module class from a module entry.

    For a ``DynamicModule``, returns the ``module`` field.
    For a module class, returns the class itself.
    """
    if isinstance(entry, DynamicModule):
        return entry.module
    return entry


def resolve_module_input(
    entry: type | DynamicModule,
) -> tuple[type, ModuleMetadata | None, bool]:
    """Normalize a module input to ``(module_class, metadata, is_dynamic)``.

    Used by the ``ModuleCompiler`` to uniformly handle both static
    module classes and :class:`DynamicModule` descriptors.

    Args:
        entry: A module class (decorated with ``@module``) or a
            :class:`DynamicModule` instance.

    Returns:
        A 3-tuple of:
        - The module class (identity key).
        - The :class:`ModuleMetadata` if statically decorated, else ``None``.
        - ``True`` if the entry is a :class:`DynamicModule`.

    Raises:
        ModuleError: If *entry* is neither a decorated module class
            nor a :class:`DynamicModule`.
    """
    if isinstance(entry, DynamicModule):
        return entry.module, None, True

    if isinstance(entry, type):
        meta = get_module_metadata(entry)
        if meta is None:
            raise ModuleError(
                f"'{entry.__name__}' is not decorated with @module. "
                f"Add @module() to the class declaration, or pass a "
                f"DynamicModule instead.",
            )
        return entry, meta, False

    raise ModuleError(
        f"Expected a module class or DynamicModule, got "
        f"{type(entry).__name__}: {entry!r}",
    )
