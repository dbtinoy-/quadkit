"""Base-URL HTTP client for outbound API communication.

A lightweight wrapper around :class:`~quadkit.http.client.HTTPClient` that
adds base-URL resolution, default-header merging, and a context-manager
lifecycle.  Returns :class:`~quadkit.contracts.web.models.HttpResponse`
directly from verb methods (raising on infrastructure failures rather than
returning a :class:`~quadkit.result.Result`).

Intended use: LLM provider adapters and other outbound SDK-style callers that
build a client once, set a base URL and default credentials, then make many
relative-path requests.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Self

from quadkit.contracts.web.http_models import HttpResponse, HttpStatusError
from quadkit.http.client._streaming import StreamResponse
from quadkit.http.client.http_client import HTTPClient
from quadkit.http.config import ConnectionPoolConfig, HTTPClientConfig
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    import aiohttp

    from quadkit.contracts.infra.resilience.protocols import (
        CircuitBreakerProtocol,
        RetryPolicyProtocol,
    )

logger = get_logger(__name__)


class StreamContext:
    """Wraps an aiohttp response for line-oriented streaming.

    Exposes status, raise_for_status(), and aiter_lines() without
    leaking the underlying aiohttp type to callers.

    Args:
        resp: The raw aiohttp ClientResponse, owned by the enclosing
            context manager for the duration of the stream.
    """

    __slots__ = ("_resp",)

    def __init__(self, resp: aiohttp.ClientResponse) -> None:
        self._resp = resp

    @property
    def status(self) -> int:
        """HTTP status code of the response."""
        return self._resp.status

    def raise_for_status(self) -> None:
        """Raise :class:`~quadkit.contracts.web.models.HttpStatusError` for 4xx/5xx.

        Raises:
            HttpStatusError: When the status code is 400 or higher.
        """
        if self._resp.status >= 400:
            raise HttpStatusError(
                f"HTTP {self._resp.status} for {self._resp.method.upper()} {self._resp.url}",
                status=self._resp.status,
                response=HttpResponse(
                    status=self._resp.status,
                    url=str(self._resp.url),
                    method=self._resp.method.upper(),
                ),
            )

    async def aiter_lines(self) -> AsyncIterator[str]:
        """Yield decoded text lines from the streaming response body.

        Yields:
            Each line decoded from UTF-8 with trailing CR/LF stripped.
        """
        async for raw in self._resp.content:
            yield raw.decode("utf-8").rstrip("\r\n")


class BaseURLHTTPClient:
    """Async HTTP client with base-URL resolution and context-manager lifecycle.

    Wraps :class:`~quadkit.http.client.HTTPClient` and adds:

    * ``base_url`` prepended to every relative request path.
    * Default headers merged into every request.
    * Direct :class:`~quadkit.contracts.web.models.HttpResponse` returns
      from verb methods (raises on infrastructure failures rather than
      returning ``Result``).
    * :meth:`stream` async context manager for line-oriented streaming
      responses (SSE, NDJSON).
    * Lazy initialisation — no explicit ``start()`` call required; the
      underlying connection pool is created on first request and torn down
      by :meth:`close`.

    Args:
        base_url: Base URL prepended to every relative path.
        headers: Default request headers merged with per-request headers.
        timeout: Request timeout in seconds (default 300).
        name: Logical name used in log messages.
        retry: Optional retry policy injected into the underlying
            :class:`~quadkit.http.client.HTTPClient`.
        circuit_breaker: Optional circuit breaker injected into the
            underlying :class:`~quadkit.http.client.HTTPClient`.

    Example::

        async with BaseURLHTTPClient(
            base_url="https://api.example.com/v1",
            headers={"Authorization": "Bearer token"},
            timeout=60.0,
        ) as client:
            resp = await client.post("/completions", json=payload)
            resp.raise_for_status()
    """

    def __init__(
        self,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        timeout: float = 300.0,
        name: str = "base-url-http-client",
        retry: RetryPolicyProtocol | None = None,
        circuit_breaker: CircuitBreakerProtocol | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/") if base_url else ""
        self.headers: dict[str, str] = dict(headers or {})
        self._timeout = timeout
        self._name = name
        self._retry = retry
        self._circuit_breaker = circuit_breaker
        self._client: HTTPClient | None = None
        self._lock: asyncio.Lock = asyncio.Lock()

    # -- URL / header helpers -----------------------------------------------

    def _resolve_url(self, path: str) -> str:
        """Resolve *path* against :attr:`_base_url`."""
        if not path:
            return self._base_url
        if path.startswith(("http://", "https://")):
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self._base_url}{path}"

    def _merge_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Return merged headers: defaults overridden by *extra*."""
        merged = dict(self.headers)
        if extra:
            merged.update(extra)
        return merged

    # -- Lifecycle ----------------------------------------------------------

    async def _get_or_create(self) -> HTTPClient:
        """Return the started HTTPClient, creating it lazily on first call."""
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    config = HTTPClientConfig(
                        pool=ConnectionPoolConfig(timeout=self._timeout)
                    )
                    self._client = HTTPClient(
                        config=config,
                        retry_policy=self._retry,
                        circuit_breaker=self._circuit_breaker,
                    )
                    await self._client.start()
                    logger.debug(
                        "base_url_client_started",
                        name=self._name,
                        base_url=self._base_url,
                    )
        return self._client

    async def close(self) -> None:
        """Stop the underlying HTTP client and release all connections."""
        async with self._lock:
            if self._client is not None:
                await self._client.stop()
                self._client = None
                logger.debug("base_url_client_stopped", name=self._name)

    async def stop(self) -> None:
        """Alias for :meth:`close`."""
        await self.close()

    async def __aenter__(self) -> Self:
        """Context manager entry — returns self (lazy init on first request)."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit — closes the underlying client."""
        await self.close()

    # -- Request methods ----------------------------------------------------

    async def request(self, method: str, url: str, **kwargs: Any) -> HttpResponse:
        """Make an HTTP request, returning :class:`~quadkit.contracts.web.models.HttpResponse` directly.

        Infrastructure failures are raised as exceptions (not wrapped in
        ``Result``).  HTTP 4xx/5xx responses are returned as-is; call
        :meth:`~quadkit.contracts.web.models.HttpResponse.raise_for_status`
        to convert them to exceptions when desired.

        Args:
            method: HTTP method (GET, POST, …).
            url: Relative path or absolute URL.
            **kwargs: Forwarded to aiohttp (``json=``, ``data=``,
                ``headers=``, …).

        Returns:
            Framework :class:`~quadkit.contracts.web.models.HttpResponse`.
        """
        client = await self._get_or_create()
        full_url = self._resolve_url(url)
        merged_headers = self._merge_headers(kwargs.pop("headers", None))
        return await client.request(method, full_url, headers=merged_headers, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform a GET request.

        Args:
            url: Relative path or absolute URL.
            **kwargs: Forwarded to aiohttp.

        Returns:
            Framework :class:`~quadkit.contracts.web.models.HttpResponse`.
        """
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, data: Any = None, **kwargs: Any) -> HttpResponse:
        """Perform a POST request.

        Args:
            url: Relative path or absolute URL.
            data: Optional body.  ``dict`` is sent as JSON; other types as
                raw ``data``.  Use ``json=`` kwarg for explicit JSON.
            **kwargs: Forwarded to aiohttp.

        Returns:
            Framework :class:`~quadkit.contracts.web.models.HttpResponse`.
        """
        if isinstance(data, dict):
            kwargs["json"] = data
        elif data is not None:
            kwargs["data"] = data
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform a PUT request.

        Args:
            url: Relative path or absolute URL.
            **kwargs: Forwarded to aiohttp.

        Returns:
            Framework :class:`~quadkit.contracts.web.models.HttpResponse`.
        """
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform a DELETE request.

        Args:
            url: Relative path or absolute URL.
            **kwargs: Forwarded to aiohttp.

        Returns:
            Framework :class:`~quadkit.contracts.web.models.HttpResponse`.
        """
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform a PATCH request.

        Args:
            url: Relative path or absolute URL.
            **kwargs: Forwarded to aiohttp.

        Returns:
            Framework :class:`~quadkit.contracts.web.models.HttpResponse`.
        """
        return await self.request("PATCH", url, **kwargs)

    @asynccontextmanager
    async def stream_response(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> AsyncIterator[StreamResponse]:
        """Stream a relative URL with status, headers and raw body chunks.

        This is the base-URL counterpart to
        :meth:`quadkit.http.client.HTTPClient.stream_response`. It keeps the
        response metadata visible to protocol gateways while preserving the
        client's default URL and header policy.
        """
        http_client = await self._get_or_create()
        full_url = self._resolve_url(url)
        merged_headers = self._merge_headers(kwargs.pop("headers", {}))
        async with http_client.stream_response(
            method,
            full_url,
            headers=merged_headers,
            **kwargs,
        ) as response:
            yield response

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> AsyncIterator[StreamContext]:
        """Async context manager for line-oriented streaming responses.

        Opens a persistent HTTP connection and wraps the response in a
        :class:`StreamContext` that exposes :meth:`~StreamContext.aiter_lines`
        for consuming SSE / NDJSON streams — the dominant format used by LLM
        provider streaming APIs.

        Args:
            method: HTTP method (typically ``"POST"`` for LLM completions).
            url: Relative path or absolute URL.
            **kwargs: Forwarded to aiohttp (``json=``, ``data=``,
                ``headers=``, …).

        Yields:
            :class:`StreamContext` with :attr:`~StreamContext.status`,
            :meth:`~StreamContext.raise_for_status`, and
            :meth:`~StreamContext.aiter_lines`.

        Example::

            async with client.stream("POST", "/chat/completions", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        ...
        """
        http_client = await self._get_or_create()
        full_url = self._resolve_url(url)
        merged_headers = self._merge_headers(kwargs.pop("headers", {}))
        pool = http_client._pool
        if pool.session is None:
            raise RuntimeError(
                f"BaseURLHTTPClient '{self._name}': connection pool session is None."
            )
        await http_client._assert_url_safe(full_url)
        async with pool.session.request(  # type: ignore[attr-defined]
            method, full_url, headers=merged_headers, **kwargs
        ) as resp:
            yield StreamContext(resp)


__all__ = ["BaseURLHTTPClient", "StreamContext"]
