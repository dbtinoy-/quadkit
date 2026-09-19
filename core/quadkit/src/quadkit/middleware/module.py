"""Middleware module for dependency injection."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.web.protocols import ExceptionFilterChainProtocol
from quadkit.di.module import DynamicModule, Module, module
from quadkit.middleware.core.chain import MiddlewareChain
from quadkit.middleware.di.provider import MiddlewareProvider


@module(
    providers=[MiddlewareProvider],
    exports=[MiddlewareChain, ExceptionFilterChainProtocol],
)
class MiddlewareModule(Module):
    """Composable async middleware pipeline, exception filter chain, and request pipeline.

    Call :meth:`configure` to configure the middleware subsystem with custom settings.

    Usage::

        from quadkit.middleware.config import MiddlewareConfig

        @module(
            imports=[MiddlewareModule.configure(MiddlewareConfig(...))]
        )
        class AppModule(Module):
            pass
    """

    @classmethod
    def configure(cls, config: Any | None = None) -> DynamicModule:
        """Create a MiddlewareModule with explicit configuration.

        Args:
            config: :class:`~quadkit.middleware.config.MiddlewareConfig` or ``None``
                for framework defaults.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        return DynamicModule(
            module=cls,
            providers=[MiddlewareProvider()],
            exports=[MiddlewareChain, ExceptionFilterChainProtocol],
        )

    @classmethod
    def stub(cls, config: Any | None = None) -> DynamicModule:
        """Return a MiddlewareModule with framework defaults for testing.

        All middleware uses default configuration. No request pipeline
        is active — only the DI bindings are registered.

        Args:
            config: Accepted for interface compatibility with
                :meth:`~quadkit.di.module.base.Module.stub`; ignored.
                Pass :class:`~quadkit.middleware.config.MiddlewareConfig`
                to :meth:`configure` instead.

        Returns:
            A DynamicModule with default middleware configuration.
        """
        return DynamicModule(
            module=cls,
            providers=[MiddlewareProvider()],
            exports=[MiddlewareChain, ExceptionFilterChainProtocol],
        )


__all__ = ["MiddlewareModule"]
