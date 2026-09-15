"""DI container package — Container, Scope, and component facades."""

from __future__ import annotations

from quadkit.di.container.container import Container
from quadkit.di.container.registrar import ContainerRegistrarImpl
from quadkit.di.container.resolver import ContainerResolverImpl
from quadkit.di.container.scope import Scope
from quadkit.di.container.validation import ContainerValidator, OrphanedRegistration

__all__ = [
    "Container",
    "ContainerRegistrarImpl",
    "ContainerResolverImpl",
    "ContainerValidator",
    "OrphanedRegistration",
    "Scope",
]
