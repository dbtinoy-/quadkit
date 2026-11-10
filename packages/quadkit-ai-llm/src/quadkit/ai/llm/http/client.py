"""Thin async HTTP client for AI model API communication.

Wraps ``aiohttp.ClientSession`` with base-URL resolution and default-header
merging.  Retry and circuit-breaker concerns belong to the caller or a
dedicated resilience layer (``the optional provider``).
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Self, cast

import aiohttp

from quadkit.contracts.web.http_models import HttpResponse, HttpStatusError
from quadkit.logging import (
    get_logger,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.contracts.infra.resilience.protocols import (
        CircuitBreakerProtocol,
        RetryPolicyProtocol,
    )

logger = get_logger(__name__)


class _StreamContext:
    """Line-oriented streaming response context for SSE/NDJSON streams.

    Wraps an :class:`aiohttp.ClientResponse` and exposes :attr:`status`,
    :meth:`raise_for_status`, and :meth:`aiter_lines` without leaking the
    underlying aiohttp type to callers.

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
                f"HTTP {self._resp.status}",
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


class ResilientHTTPClient:
    """Thin async HTTP client for LLM provider communication.

    Wraps ``aiohttp.ClientSession`` with base-URL resolution and
    default-header merging.  Optional *retry* and *circuit_breaker* instances
    from ``the optional provider`` can be injected to add retry and circuit-breaker
    protection without coupling this class to a concrete implementation.

    Args:
        base_url: Base URL prepended to every relative path.
        headers: Default request headers merged with per-request headers.
        timeout: Total request timeout in seconds.
        name: Logical name used in log messages.
        retry: Optional retry policy applied to every request.
        circuit_breaker: Optional circuit breaker wrapping every request.
            When *retry* is also set, the retry policy wraps the circuit breaker.
    """

    def __init__(
        self,
        base_url: str = "",
        headers: dict[str, str] | None = None,
        timeout: float = 300.0,
        name: str = "ai-http-client",
        retry: RetryPolicyProtocol | None = None,
        circuit_breaker: CircuitBreakerProtocol | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.headers = headers or {}
        self.timeout = timeout
        self.name = name
        self._retry = retry
        self._circuit_breaker = circuit_breaker
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return the active session, creating it lazily on first use."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()

    def _build_url(self, path: str) -> str:
        """Resolve *path* against :attr:`base_url`."""
        if not path:
            return self.base_url
        if path.startswith(("http://", "https://")):
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"

    def _merge_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Merge *extra* headers with the client default headers."""
        merged = self.headers.copy()
        if extra:
            merged.update(extra)
        return merged

    async def _raw_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> HttpResponse:
        """Execute a raw HTTP request without any resilience wrapping."""
        full_url = self._build_url(url)
        headers = self._merge_headers(kwargs.pop("headers", None))
        session = await self._get_session()
        async with session.request(method, full_url, headers=headers, **kwargs) as resp:
            try:
                json_data: Any = await resp.json(content_type=None)
            except (ValueError, UnicodeDecodeError):
                json_data = None
            body = await resp.read()
            resp_headers = {str(k): str(v) for k, v in resp.headers.items()}
            return HttpResponse(
                status=resp.status,
                headers=resp_headers,
                body=body,
                text=body.decode("utf-8", errors="replace"),
                json=json_data,
                url=str(resp.url),
                method=method.upper(),
            )

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> HttpResponse:
        """Execute an HTTP request and return an :class:`~quadkit.contracts.web.models.HttpResponse`.

        When a *retry* policy is configured it wraps the innermost call.
        When a *circuit_breaker* is configured it is called inside the retry
        boundary.  Both, either, or neither may be active.
        """
        if self._retry is not None:
            # Retry wraps the circuit-breaker-protected call (or raw call)
            if self._circuit_breaker is not None:
                return cast(
                    "HttpResponse",
                    await self._retry.execute(
                        self._circuit_breaker.call,
                        self._raw_request,
                        method,
                        url,
                        **kwargs,
                    ),
                )
            return cast(
                "HttpResponse",
                await self._retry.execute(self._raw_request, method, url, **kwargs),
            )

        if self._circuit_breaker is not None:
            return cast(
                "HttpResponse",
                await self._circuit_breaker.call(
                    self._raw_request, method, url, **kwargs
                ),
            )

        return await self._raw_request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform a GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, data: Any = None, **kwargs: Any) -> HttpResponse:
        """Perform a POST request."""
        if isinstance(data, dict):
            kwargs["json"] = data
        elif data is not None:
            kwargs["data"] = data
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform a PUT request."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform a DELETE request."""
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform a PATCH request."""
        return await self.request("PATCH", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> HttpResponse:
        """Perform a HEAD request."""
        return await self.request("HEAD", url, **kwargs)

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> AsyncIterator[_StreamContext]:
        """Async context manager for line-oriented streaming responses.

        Opens a persistent connection and wraps the response in a
        :class:`_StreamContext` that exposes :meth:`~_StreamContext.aiter_lines`
        for consuming SSE / NDJSON streams — the format used by LLM provider
        streaming APIs.

        Args:
            method: HTTP method (typically ``"POST"`` for LLM completions).
            url: Relative path or absolute URL.
            **kwargs: Forwarded to aiohttp (``json=``, ``data=``,
                ``headers=``, …).

        Yields:
            :class:`_StreamContext` with :attr:`~_StreamContext.status`,
            :meth:`~_StreamContext.raise_for_status`, and
            :meth:`~_StreamContext.aiter_lines`.
        """
        full_url = self._build_url(url)
        headers = self._merge_headers(kwargs.pop("headers", None))
        session = await self._get_session()
        async with session.request(method, full_url, headers=headers, **kwargs) as resp:
            yield _StreamContext(resp)

    async def close(self) -> None:
        """Close the underlying ``aiohttp`` session."""
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def stop(self) -> None:
        """Alias for :meth:`close`."""
        await self.close()
