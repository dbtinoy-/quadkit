"""Convention followed: **Controller pattern** — stateless HTTP adapters.
The provider constructs the controller at boot with its dependencies and
rebinds it in the container; handlers stay trivial and delegate to the
service.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.web import Controller, get

if TYPE_CHECKING:
    from http_side.services.upstream import UpstreamService


class UpstreamController(Controller):
    """Three routes: describe the demo, proxy the upstream echo, proxy a status."""

    prefix = "/"

    def __init__(self, service: UpstreamService | None = None) -> None:
        self._service = service

    @get("/")
    async def index(self) -> dict[str, Any]:
        """Describe this demo's surface (the hub mounts it at ``/examples/<slug>/``)."""
        return {
            "demo": "http-client",
            "summary": "Outbound calls with quadkit-http against an in-process mock upstream.",
            "endpoints": ["GET /upstream/echo", "GET /upstream/status/{code}"],
        }

    @get("/upstream/echo")
    async def echo(self) -> dict[str, Any]:
        """Call the upstream's ``/echo`` through the quadkit-http client."""
        assert self._service is not None
        return await self._service.fetch_echo()

    @get("/upstream/status/{code}")
    async def status(self, code: int) -> dict[str, Any]:
        """Call the upstream's ``/status/{code}`` and report the real status."""
        assert self._service is not None
        return await self._service.fetch_status(code)


__all__ = ["UpstreamController"]
