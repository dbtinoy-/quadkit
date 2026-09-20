"""Testing module for dependency injection."""

from __future__ import annotations

from typing import Any

from quadkit.di.module import DynamicModule, Module, module


@module()
class TestingModule(Module):
    """Testing utilities and fixtures module.

    Provides test doubles, container overrides, and lifecycle trackers
    for use in tests.

    Usage::

        @module(imports=[TestingModule.configure()])
        class TestAppModule(Module):
            pass
    """

    @classmethod
    def configure(cls, **kwargs: Any) -> DynamicModule:
        """Create a TestingModule for use in test suites.

        Args:
            **kwargs: Additional keyword arguments forwarded to provider setup.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        return DynamicModule(
            module=cls,
            providers=[],
            exports=[],
        )


__all__ = ["TestingModule"]
