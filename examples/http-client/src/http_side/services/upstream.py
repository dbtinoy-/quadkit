"""Convention followed: **Service layer** — the outbound HTTP lives in a
service the controller adapts; the controller stays a thin HTTP shell.

The service drives ``quadkit-http``'s real client against the in-process
mock upstream. Each call is a genuine loopback HTTP round-trip; the client's
verb methods return a ``Result``, so the service unwraps it into a plain
payload the controller can serialise.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.http.client.http_client import HTTPClient

    from http_side.mock.upstream import MockUpstream


class UpstreamService:
    """Call the mock upstream through the quadkit-http client."""

    def __init__(self, *, client: HTTPClient, upstream: MockUpstream) -> None:
        self._client = client
        self._upstream = upstream

    async def fetch_echo(self) -> dict[str, Any]:
        """GET the upstream's ``/echo`` and return its status + body."""
        return await self._get("/echo")

    async def fetch_status(self, code: int) -> dict[str, Any]:
        """GET the upstream's ``/status/{code}`` and report the real status."""
        return await self._get(f"/status/{code}")

    async def _get(self, path: str) -> dict[str, Any]:
        url = f"{self._upstream.base_url}{path}"
        result = await self._client.get(url)
        if result.is_ok():
            response = result.unwrap()
            return {"status": response.status, "json": response.json}
        error = result.unwrap_err()
        return {"status": getattr(error, "status", None), "error": str(error)}


__all__ = ["UpstreamService"]
