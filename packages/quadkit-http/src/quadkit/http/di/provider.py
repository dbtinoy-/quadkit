"""DI provider for the quadkit.http module.

Registers :class:`~quadkit.http.HTTPClient` as a container-managed singleton
and resolves resilience dependencies (retry policy, circuit breaker) from the
container at boot time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self

from quadkit.contracts.core import HealthCheckResult, HealthStatus, ProviderPriority
from quadkit.contracts.infra.resilience import (
    CircuitBreakerProtocol,
    ResiliencePipelineProtocol,
    RetryPolicyProtocol,
)
from quadkit.contracts.web import HTTPClientProtocol
from quadkit.di.provider import Provider
from quadkit.http.client import HTTPClient
from quadkit.http.config import HTTPClientConfig

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )


class HTTPProvider(Provider):
    """Framework provider for the HTTP client.

    Registers :class:`~quadkit.http.HTTPClient` (and its
    :class:`~quadkit.contracts.web.HTTPClientProtocol` binding) as a
    container-scoped singleton.  Resilience dependencies are resolved from the
    container during :meth:`boot` and injected into the client — no service
    locator is used.

    Args:
        config: Optional HTTP client configuration.  Framework defaults apply
            when not provided.
    """

    name = "http"
    priority = ProviderPriority.INFRASTRUCTURE

    config_key: str | None = "http"
    config_model: type | None = HTTPClientConfig

    def __init__(self, config: HTTPClientConfig | dict[str, Any] | None = None) -> None:
        super().__init__()
        # Zero-config construction keeps ``_config`` as None so the
        # orchestrator can inject the yaml section (via ``config_key``)
        # before boot(); explicit config is honoured as-is.
        self._config: HTTPClientConfig | dict[str, Any] | None = config
        self._client: HTTPClient | None = None

    @classmethod
    def from_config(cls, config: HTTPClientConfig, **context: Any) -> Self:
        """Create provider from config object."""
        return cls(config=config)

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register :class:`HTTPClient` bindings with the container.

        Args:
            container: The DI registrar.
        """
        container.singleton(HTTPClient, self._get_client)
        container.singleton(HTTPClientProtocol, self._get_client)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        """Construct and start the HTTP client with injected resilience.

        Resolves ``RetryPolicyProtocol`` and optionally
        ``CircuitBreakerRegistryProtocol`` from the container.  Falls back to
        framework defaults when the container has no binding for them.

        Args:
            container: The DI resolver.
        """
        retry_policy: RetryPolicyProtocol | None = None
        circuit_breaker: CircuitBreakerProtocol | None = None
        resilience: ResiliencePipelineProtocol | None = None

        try:
            retry_policy = await container.resolve(RetryPolicyProtocol)
        except Exception:  # noqa: BLE001, S110 — resilience not registered, use default
            pass

        try:
            from quadkit.contracts.infra.resilience import (
                CircuitBreakerRegistryProtocol,
            )

            registry = await container.resolve(CircuitBreakerRegistryProtocol)
            circuit_breaker = await registry.get_or_create("http-default", None)
        except Exception:  # noqa: BLE001, S110 — circuit breaker optional
            pass

        try:
            resilience = await container.resolve(ResiliencePipelineProtocol)
        except Exception:  # noqa: BLE001, S110 — resilience pipeline optional
            pass

        cfg = self._config
        if isinstance(cfg, dict):
            cfg = HTTPClientConfig(**cfg)
        if cfg is None:
            # No yaml section was injected — use framework defaults.
            cfg = HTTPClientConfig()
        self._config = cfg

        self._client = HTTPClient(
            config=cfg,
            retry_policy=retry_policy,
            circuit_breaker=circuit_breaker,
            resilience=resilience,
        )
        await self._client.start()

    async def shutdown(self) -> None:
        """Stop and dispose the HTTP client."""
        if self._client is not None:
            await self._client.stop()
            self._client = None

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return the health of the HTTP provider.

        Args:
            timeout: Unused; retained for interface compatibility.

        Returns:
            :class:`HealthCheckResult` reflecting whether the client is active.
        """
        started = self._client is not None and self._client._pool.is_started()
        return HealthCheckResult(
            component="http",
            status=HealthStatus.HEALTHY if started else HealthStatus.UNHEALTHY,
            details={"started": started},
        )

    def _get_client(self) -> HTTPClient:
        """Return the booted client; raises if :meth:`boot` has not been called."""
        if self._client is None:
            raise RuntimeError(
                "HTTPProvider has not been booted. "
                "Call boot(container) before resolving HTTPClient."
            )
        return self._client


__all__ = ["HTTPProvider"]
