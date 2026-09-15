"""DI Provider for the middleware subsystem.

Registers :class:`~quadkit.middleware.chain.MiddlewareChain` and
:class:`~quadkit.middleware.exception_filters.ExceptionFilterChain`
as container singletons and discovers third-party middleware providers
registered under the ``quadkit.middleware`` entry-point group.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import time
from typing import TYPE_CHECKING, Any

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.di.provider import Provider, ProviderPriority
from quadkit.logging import get_logger
from quadkit.middleware.core.chain import MiddlewareChain
from quadkit.middleware.core.exception_filters import ExceptionFilterChain

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        BootContainerProtocol,
        ContainerRegistrarProtocol,
    )

logger = get_logger(__name__)

_EP_GROUP = "quadkit.middleware"


class MiddlewareProvider(Provider):
    """Middleware chain, pipeline, and registry DI provider.

    On ``register()``:
      - Registers ``MiddlewareChain``, ``ExceptionFilterChain``, and
        ``MiddlewarePipeline`` as container singletons.
      - Scans the ``quadkit.middleware`` entry-point group and delegates
        registration to every discovered ``Provider`` subclass so that
        third-party middleware packages integrate automatically.
    """

    name = "middleware"
    priority = ProviderPriority.INFRASTRUCTURE

    def __init__(self) -> None:
        super().__init__()
        self._chain: MiddlewareChain | None = None
        self._filter_chain: ExceptionFilterChain | None = None
        self._discovered_providers: list[Provider] = []

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register middleware singletons and discover third-party providers.

        Args:
            container: The DI container registrar.
        """
        from quadkit.app.pipeline import MiddlewarePipeline
        from quadkit.contracts.web.protocols import ExceptionFilterChainProtocol

        mw_chain = MiddlewareChain()
        self._chain = mw_chain
        container.singleton(MiddlewareChain, mw_chain)

        chain = ExceptionFilterChain()
        self._filter_chain = chain
        container.singleton(ExceptionFilterChainProtocol, chain)
        container.singleton(ExceptionFilterChain, chain)

        container.singleton(MiddlewarePipeline, MiddlewarePipeline())

        await self._discover_providers(container)

    async def _discover_providers(self, container: ContainerRegistrarProtocol) -> None:
        """Scan the ``quadkit.middleware`` entry-point group.

        Each entry point that resolves to a :class:`~quadkit.di.provider.Provider`
        subclass is instantiated and its :meth:`~quadkit.di.provider.Provider.register`
        method is called so that it can contribute additional middleware to the
        container.

        Args:
            container: The DI container registrar.
        """
        eps = importlib.metadata.entry_points(group=_EP_GROUP)
        for ep in eps:
            try:
                candidate = ep.load()
            except Exception as exc:  # noqa: BLE001 — third-party plugin can raise anything
                logger.warning(
                    "middleware_ep_load_failed",
                    entry_point=ep.name,
                    group=_EP_GROUP,
                    error=str(exc),
                )
                continue

            if not (isinstance(candidate, type) and issubclass(candidate, Provider)):
                logger.debug(
                    "middleware_ep_skipped",
                    entry_point=ep.name,
                    reason="not a Provider subclass",
                )
                continue

            logger.debug(
                "middleware_ep_found", entry_point=ep.name, provider=candidate.__name__
            )
            try:
                provider = candidate()
                await provider.register(container)
                self._discovered_providers.append(provider)
            except Exception as exc:  # noqa: BLE001 — third-party plugin can raise anything
                logger.warning(
                    "middleware_ep_register_failed",
                    entry_point=ep.name,
                    provider=candidate.__name__,
                    error=str(exc),
                )

    async def boot(self, container: BootContainerProtocol) -> None:
        """Boot discovered providers after middleware chains are initialized.

        Args:
            container: The DI container for boot phase.
        """
        for provider in self._discovered_providers:
            await provider.boot(container)

    async def shutdown(self) -> None:
        """Shut down discovered providers in reverse order.

        Providers are shut down in reverse discovery order to respect dependency
        cleanup semantics (last booted = first shut down).
        """
        for provider in reversed(self._discovered_providers):
            await provider.shutdown()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check provider health.

        Args:
            timeout: Maximum seconds to wait for health check response.

        Returns:
            HealthCheckResult with status and component details.
        """

        start = time.perf_counter()

        details: dict[str, Any] = {}
        status = HealthStatus.HEALTHY

        try:
            async with asyncio.timeout(timeout):
                chain: Any = getattr(self, "_chain", None)
                filter_chain: Any = getattr(self, "_filter_chain", None)
                details["middleware_count"] = len(chain) if chain else 0
                details["filter_count"] = len(filter_chain) if filter_chain else 0

                if chain is not None and len(chain) == 0:
                    status = HealthStatus.DEGRADED
                    details["warning"] = "no middleware registered"
        except TimeoutError:
            return HealthCheckResult(
                component="middleware",
                status=HealthStatus.UNHEALTHY,
                error=f"health check timed out after {timeout}s",
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:  # noqa: BLE001 — a health check must never raise — report unhealthy
            status = HealthStatus.UNHEALTHY
            details["error"] = str(exc)

        return HealthCheckResult(
            component="middleware",
            status=status,
            details=details,
            duration_ms=(time.perf_counter() - start) * 1000,
        )


__all__ = ["MiddlewareProvider"]
