"""Domain module for dependency injection."""

from __future__ import annotations

from typing import Any

from quadkit.di.module import DynamicModule, Module, module


@module()
class DomainModule(Module):
    """DDD domain primitives for the Quadkit Framework.

    Domain primitives (entities, value objects, aggregates) are pure Python
    with no infrastructure dependencies — this module has no DI provider
    and requires no IoC registration. It exists for IoC graph completeness
    and future extensibility.

    Usage::

        from quadkit.domain import Entity, ValueObject, AggregateRoot

        class User(Entity):
            name: str
            email: str
    """

    @classmethod
    def configure(cls) -> DynamicModule:
        """Return a DynamicModule for IoC registration.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` with no providers.
        """
        return DynamicModule(
            module=cls,
            providers=[],
            exports=[],
        )

    @classmethod
    def stub(cls, config: Any = None) -> DynamicModule:
        """Return a test-safe DynamicModule for IoC registration."""
        return cls.configure()


__all__ = ["DomainModule"]
