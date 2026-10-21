"""HTTP session adapters bridging authlib to ``HTTPClientProtocol``.

Collaborators of :mod:`quadkit.auth.authn.oauth2`: they normalise requests
and responses from any HTTP library (aiohttp, httpx, …) into the interface
authlib expects, keeping the OAuth2 layer transport-agnostic.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from inspect import isawaitable
import sys
from typing import TYPE_CHECKING, Any, Self, cast
from urllib.parse import urlencode

from quadkit import serialization

if TYPE_CHECKING:
    from quadkit.contracts.web import HTTPClientProtocol


class QuadkitConnectSession:
    """Session adapter for authlib that delegates to ``HTTPClientProtocol``.

    Bridges authlib's internal session interface to Quadkit's
    ``HTTPClientProtocol`` contract so the OAuth2 layer remains independent
    of the underlying HTTP library (aiohttp, httpx, …).
    """

    def __init__(self, http_client: HTTPClientProtocol | None):
        self._http_client = http_client

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> QuadkitConnectResponse:
        """Make a request using the injected ``HTTPClientProtocol``."""
        if self._http_client is None:
            raise RuntimeError("HTTP client not configured for QuadkitConnectSession")

        request_method = method.upper()
        request_url = url
        request_headers = dict(kwargs.get("headers") or {})
        request_data = kwargs.get("data")
        if request_data is None and "content" in kwargs:
            request_data = kwargs["content"]

        # Authlib's OAuth2ClientAuth uses ``prepare`` to attach credentials.
        # Applying it here keeps token formatting in Authlib while the actual
        # network request still travels through QuadKit's HTTPClientProtocol.
        auth = kwargs.get("auth")
        prepare = getattr(auth, "prepare", None)
        if callable(prepare):
            if isinstance(request_data, Mapping):
                request_data = urlencode(request_data, doseq=True)
            request_url, prepared_headers, request_data = prepare(
                request_method,
                request_url,
                request_headers,
                request_data or "",
            )
            request_headers = dict(prepared_headers)
        elif isinstance(auth, tuple) and len(auth) == 2:
            credentials = f"{auth[0]}:{auth[1]}".encode("latin1")
            encoded = base64.b64encode(credentials).decode("ascii")
            request_headers.setdefault("Authorization", f"Basic {encoded}")

        client_kwargs: dict[str, Any] = {"headers": request_headers}
        if request_data is not None:
            client_kwargs["data"] = request_data
        for name in ("json", "params", "timeout", "allow_redirects", "cookies"):
            if name in kwargs:
                client_kwargs[name] = kwargs[name]

        response = await self._http_client.request(
            request_method,
            request_url,
            **client_kwargs,
        )
        return QuadkitConnectResponse(response)

    async def get(self, url: str, **kwargs: Any) -> QuadkitConnectResponse:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> QuadkitConnectResponse:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> QuadkitConnectResponse:
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> QuadkitConnectResponse:
        return await self.request("DELETE", url, **kwargs)

    async def patch(self, url: str, **kwargs: Any) -> QuadkitConnectResponse:
        return await self.request("PATCH", url, **kwargs)

    async def head(self, url: str, **kwargs: Any) -> QuadkitConnectResponse:
        return await self.request("HEAD", url, **kwargs)


def _async_byte_stream(request: Any, body: bytes) -> Any:
    """Build an in-memory async stream in the *same* httpx flavour as ``request``.

    Two things have to line up here, and getting either wrong fails at runtime
    rather than at import time:

    - ``Response(content=...)`` attaches a *sync* ``ByteStream``, while
      ``AsyncClient.send`` asserts ``isinstance(response.stream,
      AsyncByteStream)``. An async transport must therefore pass ``stream=``
      explicitly.
    - Authlib's ``AsyncOAuth2Client`` is built against whichever httpx the
      environment resolved (``httpx`` and ``httpx2`` are separate modules with
      unrelated ``AsyncByteStream`` classes), so the response has to be
      constructed from the request's own module. Building an ``httpx.Response``
      for an ``httpx2`` client satisfies neither check.
    """
    module = sys.modules[type(request).__module__.split(".")[0]]
    stream_cls = type(
        "_InMemoryAsyncByteStream",
        (module.AsyncByteStream,),
        {
            "__init__": lambda self, payload: setattr(self, "_body", payload),
            "__aiter__": lambda self: _aiter_single(self._body),
            "aclose": _aclose_noop,
        },
    )
    return stream_cls(body)


async def _aclose_noop(self: Any) -> None:
    """Nothing to release; the body is already buffered in memory."""


async def _aiter_single(body: bytes) -> Any:
    """Yield an already-buffered body exactly once."""
    yield body


class QuadkitConnectTransport:
    """HTTPX transport that delegates requests to ``HTTPClientProtocol``.

    Authlib's async OAuth client is an HTTPX client, so assigning its legacy
    ``session`` attribute does not intercept HTTPX requests. This transport is
    the supported injection point: Authlib still prepares OAuth requests and
    responses, while QuadKit retains ownership of outbound networking,
    resilience, URL safety, and response normalization.
    """

    def __init__(self, http_client: HTTPClientProtocol) -> None:
        self._http_client = http_client

    async def handle_async_request(self, request: Any) -> Any:
        """Send an HTTPX request using the injected QuadKit transport."""
        httpx_module = sys.modules[type(request).__module__.split(".")[0]]
        Response = httpx_module.Response

        request_body = await request.aread()
        request_kwargs: dict[str, Any] = {"headers": dict(request.headers)}
        if request_body:
            request_kwargs["data"] = request_body

        timeout = request.extensions.get("timeout", {})
        if isinstance(timeout, Mapping):
            read_timeout = timeout.get("read")
            if isinstance(read_timeout, (int, float)):
                request_kwargs["timeout"] = read_timeout

        response = await self._http_client.request(
            request.method,
            str(request.url),
            **request_kwargs,
        )
        content = getattr(response, "body", b"") or b""
        if not content:
            text = getattr(response, "text", "")
            content = text.encode("utf-8") if text else b""
        if not content:
            payload = getattr(response, "json", None)
            if payload is not None:
                content = serialization.dumps(payload)

        return Response(
            status_code=getattr(
                response, "status_code", getattr(response, "status", 200)
            ),
            headers=getattr(response, "headers", {}),
            stream=_async_byte_stream(request, content),
            request=request,
        )

    async def aclose(self) -> None:
        """Leave the injected client open; its owner manages its lifecycle."""


class QuadkitConnectResponse:
    """Response adapter that makes any HTTP response compatible with authlib.

    Normalises response objects from different HTTP libraries
    (aiohttp, httpx, …) into the interface expected by authlib.
    """

    def __init__(self, response: Any):
        self._response = response

    @property
    def status_code(self) -> int:
        # httpx exposes `.status_code`; aiohttp exposes `.status`.
        # Check both, preferring `.status_code`, and accept only genuine ints
        # so that MagicMock auto-attributes (not ints) are skipped correctly.
        for attr in ("status_code", "status"):
            code = getattr(self._response, attr, None)
            if isinstance(code, int):
                return code
        raise AttributeError(
            f"Response object {type(self._response).__name__!r} has no "
            f"integer 'status_code' or 'status' attribute"
        )

    @property
    def headers(self) -> dict[str, str]:
        return {str(k): str(v) for k, v in dict(self._response.headers).items()}

    async def json(self) -> dict[str, Any]:
        """Return parsed JSON from async, sync, or framework responses."""
        value = getattr(self._response, "json", None)
        if callable(value):
            value = value()
        if isawaitable(value):
            value = await value
        # QuadKit's HttpResponse stores parsed JSON as a value rather than a
        # callable method; authlib-facing adapters still expose one stable
        # awaitable method for both response shapes.
        return cast("dict[str, Any]", value)

    async def text(self) -> str:
        """Return response text from async, sync, or framework responses."""
        value = getattr(self._response, "text", "")
        if callable(value):
            value = value()
        if isawaitable(value):
            value = await value
        return str(value)

    def raise_for_status(self) -> None:
        self._response.raise_for_status()

    async def close(self) -> None:
        """Close the underlying response if the client supports it."""
        close = getattr(self._response, "close", None) or getattr(
            self._response, "release", None
        )
        if callable(close):
            result = close()
            if isawaitable(result):
                await result

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()


__all__ = [
    "QuadkitConnectResponse",
    "QuadkitConnectSession",
    "QuadkitConnectTransport",
]
