"""Async HTTP client for quadkit core.

Provides :class:`HTTPClient` — a transport-agnostic, resilience-aware client
backed by ``aiohttp``. All resilience components (retry policy, circuit breaker)
are injected as constructor parameters; no service-locator look-ups are
performed at request time.

Result semantics (verb methods only):
    - Http 2xx response  → ``Ok(HttpResponse)``
    - Http 4xx/5xx response → ``Err(HTTPStatusError)``
    - Connection / timeout failures → ``Err(HTTPConnectionError | HTTPTimeoutError)``
    - Circuit-breaker open or retries exhausted → raised as exceptions
      (infrastructure-level failures; callers should not normally recover).
"""

from __future__ import annotations

import asyncio
import ipaddress
from typing import TYPE_CHECKING, Any
import urllib.parse

import aiohttp

if TYPE_CHECKING:
    from collections.abc import Iterable

    from quadkit.contracts.observability.metrics import MetricsRecorderProtocol

from yarl import URL

from quadkit.contracts.infra.resilience import (
    CircuitBreakerError as _CoreCircuitBreakerError,
)
from quadkit.contracts.infra.resilience import (
    CircuitBreakerProtocol,
    ResiliencePipelineProtocol,
    RetryPolicyProtocol,
)
from quadkit.contracts.infra.resilience import (
    RetryError as _CoreRetryError,
)
from quadkit.contracts.security import collect_safe_addresses
from quadkit.contracts.web import HttpResponse, InterceptorProtocol
from quadkit.http.config import HTTPClientConfig
from quadkit.http.exceptions import (
    HTTPCircuitOpenError,
    HTTPClientError,
    HTTPConnectionError,
    HTTPRetryExhaustedError,
    HTTPTimeoutError,
    HTTPUnsafeURLError,
)
from quadkit.http.pool import ConnectionPool
from quadkit.http.types import RequestContext
from quadkit.logging import get_logger

logger = get_logger(__name__)

_CIRCUIT_OPEN_CODE = "QK_ERR_RES_009"
_RETRY_EXHAUSTED_CODE = "QK_ERR_RES_008"


def _is_retry_exhausted_error(exc: BaseException) -> bool:
    """Return whether *exc* represents a retry-exhausted failure."""

    return (
        isinstance(exc, _CoreRetryError)
        and getattr(exc, "code", None) == _RETRY_EXHAUSTED_CODE
    )


def _is_circuit_open_error(exc: BaseException) -> bool:
    """Return whether *exc* represents an open-circuit failure."""

    return (
        isinstance(exc, _CoreCircuitBreakerError)
        and getattr(exc, "code", None) == _CIRCUIT_OPEN_CODE
    )


async def _to_http_response(raw: Any, method: str) -> HttpResponse:
    """Convert an ``aiohttp.ClientResponse`` to a framework-owned :class:`HttpResponse`.

    Reads the body eagerly so the response can be used after the connection is
    released back to the pool.

    Args:
        raw: The raw ``aiohttp`` response to convert.
        method: Upper-cased HTTP method of the original request.

    Returns:
        A fully-populated :class:`HttpResponse` instance.
    """
    body = await raw.read()
    text = body.decode(raw.get_encoding() or "utf-8", errors="replace")
    json_data: Any = None
    content_type = raw.headers.get("Content-Type", "")
    if "application/json" in content_type or "text/json" in content_type:
        try:
            json_data = await raw.json(content_type=None)
        except Exception:  # noqa: BLE001, S110 — non-JSON body is not an error
            pass
    return HttpResponse(
        status=raw.status,
        headers=dict(raw.headers),
        body=body,
        text=text,
        json=json_data,
        url=str(raw.url),
        method=method.upper(),
    )


from quadkit.http.client._streaming import _HTTPStreamingMixin
from quadkit.http.client._verbs import _HTTPVerbsMixin


class HTTPClient(
    _HTTPStreamingMixin,
    _HTTPVerbsMixin,
):
    """Async HTTP client with connection pooling and optional resilience.

    All dependencies are provided at construction time (constructor injection).
    When used through :class:`~quadkit.http.HTTPProvider`, ``retry_policy``
    and ``circuit_breaker`` are resolved from the container and injected here.
    For standalone usage, pass them directly or accept the defaults.

    Args:
        config: Pool and client configuration.  Defaults to
            :class:`~quadkit.http.HTTPClientConfig` with framework defaults.
        pool: Optional pre-configured :class:`ConnectionPool`.  Created from
            *config* when not provided.
        retry_policy: Retry policy for transient failures.  Defaults to a
            :class:`~the optional provider module` with framework defaults.
        circuit_breaker: Optional circuit breaker; disabled when ``None``.
        interceptors: Zero or more interceptors applied to every request.
        resilience: Optional :class:`ResiliencePipelineProtocol` that combines
            retry, circuit-breaker, bulkhead and timeout into a single
            composable pipeline.  When provided it takes precedence over the
            individual ``retry_policy`` and ``circuit_breaker`` parameters.
        metrics: Optional :class:`~quadkit.contracts.observability.protocols.MetricsRecorderProtocol`
            for emitting ``http.request.duration`` (histogram) and
            ``http.request.status`` (counter) per-request metrics.

    Example:
        >>> config = HTTPClientConfig()
        >>> async with HTTPClient.session_context(config) as client:
        ...     response = await client.get("https://api.example.com/data")
    """

    def __init__(
        self,
        config: HTTPClientConfig | None = None,
        pool: ConnectionPool | None = None,
        retry_policy: RetryPolicyProtocol | None = None,
        circuit_breaker: CircuitBreakerProtocol | None = None,
        interceptors: Iterable[InterceptorProtocol] = (),
        resilience: ResiliencePipelineProtocol | None = None,
        metrics: MetricsRecorderProtocol | None = None,
    ) -> None:
        self._config: HTTPClientConfig = config or HTTPClientConfig()
        self._pool: ConnectionPool = pool or ConnectionPool(
            max_connections=self._config.pool.max_connections,
            max_keepalive_connections=self._config.pool.max_keepalive_connections,
            max_connections_per_host=self._config.pool.max_connections_per_host,
            timeout=self._config.pool.timeout,
            ttl_dns_cache=self._config.pool.ttl_dns_cache,
            force_close=self._config.pool.force_close,
            verify_ssl=getattr(self._config.pool, "verify_ssl", True),
            proxy=self._config.proxy,
            trust_env=self._config.trust_env,
            cookie_jar=self._config.cookie_jar,
        )
        self._resilience = resilience
        self._metrics = metrics
        # Default retry policy: local implementation - no cross-package imports
        if retry_policy is None:
            from quadkit.contracts.infra.resilience import RetryConfig
            from quadkit.http.retry import RetryPolicy

            retry_policy = RetryPolicy(config=RetryConfig())
        self._retry_policy: RetryPolicyProtocol = retry_policy
        self._circuit_breaker = circuit_breaker
        self._interceptors: list[InterceptorProtocol] = list(interceptors)

    @property
    def config(self) -> HTTPClientConfig:
        """Return the client configuration."""
        return self._config

    @property
    def pool(self) -> ConnectionPool:
        """Return the underlying connection pool."""
        return self._pool

    @pool.setter
    def pool(self, value: ConnectionPool) -> None:
        """Replace the connection pool (mainly for testing)."""
        self._pool = value

    async def start(self) -> None:
        """Start the HTTP client and its connection pool."""
        await self._pool.start()

    async def stop(self) -> None:
        """Stop the HTTP client and close the connection pool."""
        await self._pool.stop()

    async def _assert_url_safe(self, url: str) -> None:
        """Reject URLs that could reach private/reserved hosts (SSRF gate).

        When the gate passes, the validated address set is pinned into the
        connection pool's resolver so the actual connect uses exactly the
        approved addresses — closing the check-then-connect DNS-rebinding
        window (an attacker-controlled DNS cannot answer a public IP at
        validation time and a private one at connect time).

        Args:
            url: The request target URL to validate.

        Raises:
            HTTPUnsafeURLError: If the URL could reach a private or reserved host.
        """
        if not self._config.enforce_url_safety:
            return
        try:
            addresses = await asyncio.to_thread(collect_safe_addresses, url)
        except ValueError as err:
            raise HTTPUnsafeURLError(f"Unsafe URL rejected: {url!r}") from err
        host = urllib.parse.urlparse(url).hostname
        if host:
            host = host.strip("[]")
            try:
                ipaddress.ip_address(host)
            except ValueError:
                # DNS name — pin the validated set so the connect cannot
                # rebind to a different (private) address.
                self._pool.pin_dns(host, addresses)

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        """Make an HTTP request with retry and optional circuit-breaker protection.

        .. note::
            **Infrastructure-level method** — this method raises exceptions for
            all failures (circuit open, retries exhausted, connection errors).
            Use the high-level verb methods (:meth:`get`, :meth:`post`, etc.)
            in application/domain code — they return ``Result`` and avoid
            exception-based control flow for expected failures.

            Summary of the two-layer strategy:

            * ``request()`` — infrastructure layer, raises exceptions.
            * ``get()``, ``post()``, etc. — domain layer, return ``Result``.

        Args:
            method: HTTP method (``GET``, ``POST``, etc.)
            url: Target URL.
            **kwargs: Additional keyword arguments forwarded to ``aiohttp``.

        Returns:
            Framework-owned :class:`HttpResponse`.

        Raises:
            HTTPCircuitOpenError: When the circuit breaker is open.
            HTTPRetryExhaustedError: When all retry attempts are exhausted.
            HTTPConnectionError: When the connection cannot be established.
            HTTPTimeoutError: When the request times out.
        """
        # Build typed request context for interceptors
        request_ctx = RequestContext(
            method=method,
            url=url,
            headers=dict(kwargs.get("headers", {})),
        )

        # Run request interceptors
        for interceptor in self._interceptors:
            request_ctx = await interceptor.intercept_request(request_ctx)

        _method = request_ctx.method
        _url = request_ctx.url
        _kwargs = dict(kwargs)
        _kwargs["headers"] = request_ctx.headers

        # SSRF + redirect policy.  Automatic redirects are disabled; the
        # client follows Location hops itself so the SSRF gate re-validates
        # every target before a connection is attempted (spec finding 4).
        allow_redirects = _kwargs.pop("allow_redirects", None)
        max_hops = max(0, int(getattr(self._config, "max_redirects", 5)))

        # Short-circuit immediately when circuit is already open
        if self._circuit_breaker and (
            getattr(self._circuit_breaker.state, "value", self._circuit_breaker.state)
            == "open"
        ):
            raise HTTPCircuitOpenError("Circuit breaker is OPEN")

        async def _execute_one(hop_url: str) -> Any:
            session = self._pool.session
            if session is None:
                raise RuntimeError(
                    "HTTPClient not started — call await client.start() first"
                )
            hop_kwargs = dict(_kwargs)
            hop_kwargs["allow_redirects"] = (
                allow_redirects if allow_redirects is not None else False
            )
            if getattr(self._pool, "proxy", None) and "proxy" not in hop_kwargs:
                hop_kwargs["proxy"] = self._pool.proxy

            async def _call() -> Any:
                return await session.request(_method, hop_url, **hop_kwargs)

            if self._circuit_breaker:
                return await self._circuit_breaker.call(_call)
            return await _call()

        try:
            if allow_redirects is not None:
                # Caller owns redirect behavior entirely.
                await self._assert_url_safe(_url)
                raw = await (
                    self._resilience.execute(lambda: _execute_one(_url), method=_method)
                    if self._resilience is not None
                    else self._retry_policy.execute(
                        lambda: _execute_one(_url), method=_method
                    )
                )
            else:
                follows_left = max_hops
                while True:
                    await self._assert_url_safe(_url)
                    raw = await (
                        self._resilience.execute(
                            lambda url=_url: _execute_one(url), method=_method
                        )
                        if self._resilience is not None
                        else self._retry_policy.execute(
                            lambda url=_url: _execute_one(url), method=_method
                        )
                    )
                    status = getattr(raw, "status", None)
                    if status not in (301, 302, 303, 307, 308):
                        break
                    if follows_left == 0:
                        raise HTTPClientError(
                            f"Too many redirects (> {max_hops}) for {_url!r}"
                        )
                    location = getattr(raw, "headers", {}).get("Location")
                    if not location:
                        break
                    follows_left -= 1
                    release = getattr(raw, "release", None)
                    if release is not None:
                        result = release()
                        if asyncio.iscoroutine(result):
                            await result
                    _url = str(URL(_url).join(URL(location)))
        except (
            Exception
        ) as exc:  # HTTP client must normalise all resilience library exceptions
            if _is_retry_exhausted_error(exc):
                raise HTTPRetryExhaustedError(str(exc)) from exc
            if _is_circuit_open_error(exc):
                raise HTTPCircuitOpenError(str(exc)) from exc
            # TimeoutError covers asyncio.TimeoutError and aiohttp's
            # ServerTimeoutError on 3.11+ (and resilience timeout wrappers,
            # which subclass it) — normalise to the documented
            # HTTPTimeoutError so verb Result mapping works.
            if isinstance(exc, TimeoutError):
                raise HTTPTimeoutError(str(exc)) from exc
            # Remaining aiohttp client errors (connect refused/DNS/reset,
            # InvalidURL, ...) normalise to HTTPConnectionError per the
            # documented verb contract; previously they escaped raw.
            if isinstance(exc, aiohttp.ClientError):
                raise HTTPConnectionError(str(exc)) from exc
            raise

        # Run response interceptors (final response only)
        for interceptor in self._interceptors:
            raw = await interceptor.intercept_response(raw)

        return await _to_http_response(raw, method)
