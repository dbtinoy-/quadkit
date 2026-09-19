"""Mapping module for dependency injection."""

from __future__ import annotations

from quadkit.di.module import Module, module
from quadkit.mapping.core.mapper import ObjectMapperImpl
from quadkit.mapping.di.provider import MappingProvider


@module(
    providers=[MappingProvider],
    exports=[ObjectMapperImpl],
)
class MappingModule(Module):
    """Object-to-object mapping registry and mapper.

    Static module — no factory required.  Registers a shared
    :class:`~quadkit.mapping.mapper.MappingRegistry` and
    :class:`~quadkit.mapping.mapper.ObjectMapperImpl` singleton.

    Usage::

        @module(imports=[MappingModule])
        class AppModule(Module):
            pass
    """


__all__ = ["MappingModule"]
