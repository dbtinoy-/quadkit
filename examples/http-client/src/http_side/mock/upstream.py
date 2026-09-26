"""In-process mock upstream for the HTTP Client demo.

Convention followed: **repository-adjacent fixture** — a scriptable,
in-process fake stands in for a real third-party service so the demo's real
``quadkit-http`` client has something reachable to call, with no outbound
network access. Every request is still a *real* loopback HTTP round-trip;
only the "third party" on the other end is simulated.

Endpoints:

- ``GET/POST /echo``     — echoes method, path, query, and body back
- ``GET /status/{code}`` — always answers with the requested status code
"""

from __future__ import annotations

from aiohttp import web


def build_mock_app() -> web.Application:
    """Build the ``aiohttp.web`` application backing the mock upstream."""

    async def echo(request: web.Request) -> web.Response:
        body = await request.read()
        return web.json_response(
            {
                "method": request.method,
                "path": request.path,
                "query": dict(request.query),
                "body": body.decode("utf-8", errors="replace"),
            }
        )

    async def status_code(request: web.Request) -> web.Response:
        try:
            code = int(request.match_info["code"])
        except ValueError:
            return web.json_response({"error": "code must be an integer"}, status=400)
        return web.json_response({"requested_status": code}, status=code)

    app = web.Application()
    app.router.add_route("*", "/echo", echo)
    app.router.add_get("/status/{code}", status_code)
    return app


class MockUpstream:
    """Own the lifecycle of the loopback mock upstream server.

    Binds to an OS-assigned ephemeral port so it never collides with the
    demo's own web server port.
    """

    def __init__(self, host: str = "127.0.0.1") -> None:
        self._host = host
        self._runner: web.AppRunner | None = None
        self._port: int | None = None

    @property
    def base_url(self) -> str:
        """Return the mock upstream's base URL once started."""
        if self._port is None:
            raise RuntimeError("MockUpstream has not been started")
        return f"http://{self._host}:{self._port}"

    async def start(self) -> None:
        """Start the mock upstream on an ephemeral loopback port."""
        app = build_mock_app()
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, 0)
        await site.start()
        assert site._server is not None  # noqa: S101 — aiohttp guarantees this post-start()
        self._port = site._server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        """Stop the mock upstream and release its socket."""
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            self._port = None


__all__ = ["MockUpstream", "build_mock_app"]
