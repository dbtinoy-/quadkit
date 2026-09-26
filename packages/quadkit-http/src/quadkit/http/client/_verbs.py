"""Convenience verb methods (GET/POST/PUT/DELETE/PATCH/HEAD)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import time
from typing import Any

from quadkit.contracts.web import HttpResponse
from quadkit.http.exceptions import (
    HTTPClientError,
    HTTPConnectionError,
    HTTPStatusError,
    HTTPTimeoutError,
)
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)

_CIRCUIT_OPEN_CODE = "QK_ERR_RES_009"
_RETRY_EXHAUSTED_CODE = "QK_ERR_RES_008"


class _HTTPVerbsMixin:
    request: Callable[..., Coroutine[Any, Any, HttpResponse]]
    _metrics: Any
    _pool: Any
    _assert_url_safe: Callable[..., Any]

    """See :class:`HTTPClient`."""

    async def get(
        self, url: str, **kwargs: Any
    ) -> Result[HttpResponse, HTTPClientError]:
        """Perform a GET request.

        Args:
            url: Target URL.
            **kwargs: Forwarded to :meth:`request`.

        Returns:
            ``Ok(HttpResponse)`` on 2xx; ``Err(HTTPStatusError)`` on 4xx/5xx;
            ``Err(HTTPConnectionError | HTTPTimeoutError)`` on transport failure.

        Raises:
            HTTPCircuitOpenError: When the circuit breaker is open.
            HTTPRetryExhaustedError: When all retry attempts are exhausted.
        """
        return await self._request_result("GET", url, **kwargs)

    async def post(
        self, url: str, **kwargs: Any
    ) -> Result[HttpResponse, HTTPClientError]:
        """Perform a POST request.

        Args:
            url: Target URL.
            **kwargs: Forwarded to :meth:`request`.

        Returns:
            ``Ok(HttpResponse)`` on 2xx; ``Err(HTTPStatusError)`` on 4xx/5xx;
            ``Err(HTTPConnectionError | HTTPTimeoutError)`` on transport failure.

        Raises:
            HTTPCircuitOpenError: When the circuit breaker is open.
            HTTPRetryExhaustedError: When all retry attempts are exhausted.
        """
        return await self._request_result("POST", url, **kwargs)

    async def put(
        self, url: str, **kwargs: Any
    ) -> Result[HttpResponse, HTTPClientError]:
        """Perform a PUT request.

        Args:
            url: Target URL.
            **kwargs: Forwarded to :meth:`request`.

        Returns:
            ``Ok(HttpResponse)`` on 2xx; ``Err(HTTPStatusError)`` on 4xx/5xx;
            ``Err(HTTPConnectionError | HTTPTimeoutError)`` on transport failure.

        Raises:
            HTTPCircuitOpenError: When the circuit breaker is open.
            HTTPRetryExhaustedError: When all retry attempts are exhausted.
        """
        return await self._request_result("PUT", url, **kwargs)

    async def delete(
        self, url: str, **kwargs: Any
    ) -> Result[HttpResponse, HTTPClientError]:
        """Perform a DELETE request.

        Args:
            url: Target URL.
            **kwargs: Forwarded to :meth:`request`.

        Returns:
            ``Ok(HttpResponse)`` on 2xx; ``Err(HTTPStatusError)`` on 4xx/5xx;
            ``Err(HTTPConnectionError | HTTPTimeoutError)`` on transport failure.

        Raises:
            HTTPCircuitOpenError: When the circuit breaker is open.
            HTTPRetryExhaustedError: When all retry attempts are exhausted.
        """
        return await self._request_result("DELETE", url, **kwargs)

    async def patch(
        self, url: str, **kwargs: Any
    ) -> Result[HttpResponse, HTTPClientError]:
        """Perform a PATCH request.

        Args:
            url: Target URL.
            **kwargs: Forwarded to :meth:`request`.

        Returns:
            ``Ok(HttpResponse)`` on 2xx; ``Err(HTTPStatusError)`` on 4xx/5xx;
            ``Err(HTTPConnectionError | HTTPTimeoutError)`` on transport failure.

        Raises:
            HTTPCircuitOpenError: When the circuit breaker is open.
            HTTPRetryExhaustedError: When all retry attempts are exhausted.
        """
        return await self._request_result("PATCH", url, **kwargs)

    async def head(
        self, url: str, **kwargs: Any
    ) -> Result[HttpResponse, HTTPClientError]:
        """Perform a HEAD request.

        Args:
            url: Target URL.
            **kwargs: Forwarded to :meth:`request`.

        Returns:
            ``Ok(HttpResponse)`` on 2xx; ``Err(HTTPStatusError)`` on 4xx/5xx;
            ``Err(HTTPConnectionError | HTTPTimeoutError)`` on transport failure.

        Raises:
            HTTPCircuitOpenError: When the circuit breaker is open.
            HTTPRetryExhaustedError: When all retry attempts are exhausted.
        """
        return await self._request_result("HEAD", url, **kwargs)

    async def _request_result(
        self, method: str, url: str, **kwargs: Any
    ) -> Result[HttpResponse, HTTPClientError]:
        """Shared Result-returning implementation for all verb methods.

        Calls the raw :meth:`request` transport method and maps the outcome:
        - 2xx → ``Ok(HttpResponse)``
        - 4xx/5xx → ``Err(HTTPStatusError)``
        - Connection / timeout failures → ``Err(HTTPConnectionError | HTTPTimeoutError)``
        - Circuit-breaker open / retries exhausted → raised as-is (infrastructure)

        Args:
            method: HTTP method string.
            url: Target URL.
            **kwargs: Forwarded to :meth:`request`.
        """
        start = time.monotonic()
        try:
            response = await self.request(method, url, **kwargs)
        except HTTPConnectionError as exc:
            logger.debug(
                "http.client.connection_error", method=method, url=url, error=str(exc)
            )
            if self._metrics is not None:
                self._metrics.increment(
                    "http.request.status",
                    tags={"method": method.upper(), "status": "connection_error"},
                )
            return Err(exc)
        except HTTPTimeoutError as exc:
            logger.debug("http.client.timeout", method=method, url=url, error=str(exc))
            if self._metrics is not None:
                self._metrics.increment(
                    "http.request.status",
                    tags={"method": method.upper(), "status": "timeout"},
                )
            return Err(exc)
        # HTTPCircuitOpenError and HTTPRetryExhaustedError propagate as exceptions.
        finally:
            duration = time.monotonic() - start
            if self._metrics is not None:
                self._metrics.histogram(
                    "http.request.duration",
                    duration,
                    tags={"method": method.upper()},
                )

        if response.status >= 400:
            logger.debug(
                "http.client.error_response",
                method=method,
                url=url,
                status=response.status,
            )
            if self._metrics is not None:
                self._metrics.increment(
                    "http.request.status",
                    tags={"method": method.upper(), "status": str(response.status)},
                )
            return Err(HTTPStatusError(status=response.status, response=response))
        if self._metrics is not None:
            self._metrics.increment(
                "http.request.status",
                tags={"method": method.upper(), "status": str(response.status)},
            )
        return Ok(response)
