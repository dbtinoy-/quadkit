"""Dependency injection system for Quadkit Framework.

Provides the IoC container, builder, scoping, module system, provider
orchestrator, and DI decorators for constructor injection.

Exports:
    Container, Scope: Core DI container and scope.
    ContainerBuilder: Fluent API for building a configured container.
    ContainerRegistrarProtocol: Write-only container interface for Provider.register().
    ContainerResolverProtocol: Read-only container interface for Provider.boot().
    Module, module: DI module descriptor and decorator.
    Provider: Base class for all framework providers.
    ProviderOrchestrator: Coordinates provider lifecycle in priority order.
    ProviderPriority: Enum for provider registration priority.
    ResolutionStrategy: Extension hook for custom resolution logic.
    ServiceScope: Enum for singleton/scoped/transient lifetimes.
    Injectable, inject, injectable, scoped, singleton, transient: DI decorators.
"""

from __future__ import annotations

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )
    from quadkit.contracts.core.provider import ProviderPriority
    from quadkit.contracts.core.scopes import ServiceScope
    from quadkit.di.builder import ContainerBuilder
    from quadkit.di.container import Container, Scope
    from quadkit.di.context import (
        ModuleContextTokens,
        check_visibility,
        clear_module_context,
        get_current_module,
        set_module_context,
    )
    from quadkit.di.decorators import (
        Injectable,
        inject,
        injectable,
        scoped,
        singleton,
        transient,
    )
    from quadkit.di.extensions.strategies import ResolutionStrategy
    from quadkit.di.function_provider import FunctionProvider, provide
    from quadkit.di.markers import named
    from quadkit.di.module import Module, module
    from quadkit.di.orchestrator import ProviderOrchestrator
    from quadkit.di.provider import Provider

_LAZY_IMPORTS: dict[str, str] = {
    "ContainerRegistrarProtocol": "quadkit.contracts.core.di",
    "ContainerResolverProtocol": "quadkit.contracts.core.di",
    "ProviderPriority": "quadkit.contracts.core.provider",
    "Injectable": "quadkit.di.decorators",
    "inject": "quadkit.di.decorators",
    "injectable": "quadkit.di.decorators",
    "scoped": "quadkit.di.decorators",
    "singleton": "quadkit.di.decorators",
    "transient": "quadkit.di.decorators",
    "ContainerBuilder": "quadkit.di.builder",
    "Container": "quadkit.di.container",
    "Scope": "quadkit.di.container",
    "ResolutionStrategy": "quadkit.di.extensions.strategies",
    "FunctionProvider": "quadkit.di.function_provider",
    "provide": "quadkit.di.function_provider",
    "named": "quadkit.di.markers",
    "Module": "quadkit.di.module",
    "module": "quadkit.di.module",
    "ProviderOrchestrator": "quadkit.di.orchestrator",
    "Provider": "quadkit.di.provider",
    "ServiceScope": "quadkit.contracts.core.scopes",
    # types
    "ProviderState": "quadkit.di.types",
    # constants
    "DEFAULT_MAX_RESOLUTION_DEPTH": "quadkit.di.constants",
    "DEFAULT_SCOPE_NAME": "quadkit.di.constants",
    # --- added by migration script ---
    "DiConfig": "quadkit.di.config.models",
    "CircularDependencyError": "quadkit.di.exceptions",
    "ContainerBuildError": "quadkit.di.exceptions",
    "ContainerError": "quadkit.di.exceptions",
    "DependencyError": "quadkit.di.exceptions",
    "ModuleError": "quadkit.di.exceptions",
    "ProviderError": "quadkit.di.exceptions",
    "RegistrationError": "quadkit.di.exceptions",
    "UnresolvableDependencyError": "quadkit.di.exceptions",
    "DiProvider": "quadkit.di.integration.provider",
    # context
    "ModuleContextTokens": "quadkit.di.context",
    "check_visibility": "quadkit.di.context",
    "clear_module_context": "quadkit.di.context",
    "get_current_module": "quadkit.di.context",
    "set_module_context": "quadkit.di.context",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib

        mod = importlib.import_module(_LAZY_IMPORTS[name])
        return getattr(mod, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return list(_LAZY_IMPORTS.keys())


__all__ = list(_LAZY_IMPORTS.keys())
