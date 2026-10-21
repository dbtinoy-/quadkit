"""Convention followed: **Provider lifecycle** — ``register()`` declares
singletons, ``boot()`` resolves cross-module contracts and starts the
demo-owned resources, ``shutdown()`` releases them in reverse order,
``health_check()`` reports readiness.

Lifecycle wiring for the HTTP Client demo: boot the in-process mock
upstream, build a ``quadkit-http`` client pointed at it, and bind the
controller. The client talks only to the loopback upstream, so the SSRF gate
(``enforce_url_safety``) is relaxed — the posture a real internal client
takes toward a known-trusted peer.
"""

from __future__ import annotations

import dataclasses

from http_side.config import HttpSideConfig
from http_side.controllers.api import UpstreamController
from http_side.mock.upstream import MockUpstream
from http_side.services.upstream import UpstreamService
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.core.di import (
    ContainerRegistrarProtocol,
    ContainerResolverProtocol,
)
from quadkit.contracts.web import HTTPClientProtocol
from quadkit.di.provider import Provider
from quadkit.http.client.http_client import HTTPClient
from quadkit.http.retry import RetryPolicy


class HttpSideProvider(Provider):
    """Boot the mock upstream + client and bind the controller."""

    name = "http_side"
    config_key: str | None = "http_side"
    config_model: type | None = HttpSideConfig

    def __init__(self) -> None:
        super().__init__()
        self._upstream: MockUpstream | None = None
        self._client: HTTPClient | None = None

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        config = (
            self.config if isinstance(self.config, HttpSideConfig) else HttpSideConfig()
        )
        container.singleton(HttpSideConfig, config)
        container.singleton(UpstreamController, UpstreamController)

    async def boot(self, container: ContainerResolverProtocol) -> None:
        config = await container.resolve(HttpSideConfig)

        upstream = MockUpstream(host=config.upstream_host)
        await upstream.start()
        self._upstream = upstream

        # Reuse the container client's yaml-configured settings, relaxing the
        # SSRF gate so the loopback upstream is reachable.
        container_client = await container.resolve(HTTPClientProtocol)
        client = HTTPClient(
            config=dataclasses.replace(
                container_client.config, enforce_url_safety=False
            ),
            retry_policy=RetryPolicy(),
        )
        await client.start()
        self._client = client

        service = UpstreamService(client=client, upstream=upstream)
        container.bind(UpstreamController, UpstreamController(service=service))

    async def shutdown(self) -> None:
        """Stop the client and the mock upstream, in reverse order."""
        if self._client is not None:
            await self._client.stop()
            self._client = None
        if self._upstream is not None:
            await self._upstream.stop()
            self._upstream = None

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report provider wiring for framework health aggregation."""
        return HealthCheckResult(
            component=self.name,
            status=HealthStatus.HEALTHY,
            details={"demo": "http-client"},
        )


__all__ = ["HttpSideProvider"]
