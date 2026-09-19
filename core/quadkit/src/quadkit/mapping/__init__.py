"""Object mapping module for transforming between domain models and DTOs.

Exports:
    MappingRegistry: Registry that stores mapper functions keyed by (source, target) type pairs.
    ObjectMapperImpl: Mapper that resolves and invokes registered mapper functions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.mapping.core.mapper import MappingRegistry, ObjectMapperImpl
    from quadkit.mapping.exceptions import (
        MappingError as MappingError,
    )
    from quadkit.mapping.exceptions import (
        MappingExecutionError as MappingExecutionError,
    )
    from quadkit.mapping.exceptions import (
        MappingNotFoundError as MappingNotFoundError,
    )
    from quadkit.mapping.protocols import (
        TypeConverterProtocol as TypeConverterProtocol,
    )
    from quadkit.mapping.types import MapperProtocol as MapperProtocol
    from quadkit.mapping.types import MappingFn as MappingFn

_LAZY_IMPORTS: dict[str, str] = {
    "MappingRegistry": "quadkit.mapping.core.mapper",
    "ObjectMapperImpl": "quadkit.mapping.core.mapper",
    # config
    "MappingConfig": "quadkit.mapping.config",
    # exceptions
    "MappingError": "quadkit.mapping.exceptions",
    "MappingExecutionError": "quadkit.mapping.exceptions",
    "MappingNotFoundError": "quadkit.mapping.exceptions",
    # protocols (now in types)
    "MapperProtocol": "quadkit.mapping.types",
    # types
    "MappingFn": "quadkit.mapping.types",
    # provider
    "MappingModule": "quadkit.mapping.module",
    "MappingProvider": "quadkit.mapping.di.provider",
    # Internal protocols
    "TypeConverterProtocol": "quadkit.mapping.protocols",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = list(_LAZY_IMPORTS.keys())
