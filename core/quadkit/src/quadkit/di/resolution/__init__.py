"""DI resolution engine — descriptors, registry, resolver, injector, and type hints."""

from __future__ import annotations

from quadkit.di.resolution.context import current_resolver_var, get_resolver
from quadkit.di.resolution.descriptor import ServiceDescriptor
from quadkit.di.resolution.injector import DependencyInjector
from quadkit.di.resolution.registry import ServiceRegistry
from quadkit.di.resolution.resolver import ServiceResolver
from quadkit.di.resolution.store import ServiceStore
from quadkit.di.resolution.type_hints import BoundedCache, TypeHintResolverImpl
from quadkit.di.resolution.validator import GraphValidator

__all__ = [
    "BoundedCache",
    "DependencyInjector",
    "GraphValidator",
    "ServiceDescriptor",
    "ServiceRegistry",
    "ServiceResolver",
    "ServiceStore",
    "TypeHintResolverImpl",
    "current_resolver_var",
    "get_resolver",
]
