"""HTTP client module for dependency injection."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.web import HTTPClientProtocol
from quadkit.di.module import DynamicModule, Module, module
from quadkit.http.di.provider import HTTPProvider


@module()
class HTTPModule(Module):
    """Async outbound HTTP client backed by aiohttp with connection pooling.

    Call :meth:`configure` to configure the HTTP client with custom settings
    and optional resilience integration (retry, circuit breaker).

    Usage (defaults)::

        @module(imports=[HTTPModule.configure()])
        class AppModule(Module):
            pass

    Usage (configured)::

        from quadkit.http.config import HTTPClientConfig

        @module(
            imports=[HTTPModule.configure(HTTPClientConfig(timeout=30))]
        )
        class AppModule(Module):
            pass
    """

    @classmethod
    def configure(cls, config: Any | None = None) -> DynamicModule:
        """Create an HTTPModule with explicit configuration.

        Args:
            config: :class:`~quadkit.http.config.HTTPClientConfig` or ``None``
                for framework defaults.

        Returns:
            A :class:`~quadkit.di.module.DynamicModule` descriptor.
        """
        from quadkit.http.config import HTTPClientConfig

        if config is not None and not isinstance(config, HTTPClientConfig):
            raise TypeError(
                f"config must be HTTPClientConfig, got {type(config).__name__}"
            )

        return DynamicModule(
            module=cls,
            providers=[HTTPProvider(config=config)],
            exports=[HTTPClientProtocol],
        )

    @classmethod
    def stub(cls, config: Any = None) -> DynamicModule:
        """Return a no-op HTTPModule for unit testing.

        Registers an HTTP client with default configuration.
        No real outbound connections are made unless explicitly called.

        Returns:
            A DynamicModule with default HTTP client configuration.
        """
        return DynamicModule(
            module=cls,
            providers=[HTTPProvider()],
            exports=[HTTPClientProtocol],
        )


__all__ = ["HTTPModule"]
