"""Convention followed: **Page controller pattern** — static-only serving
of views plus shared brand assets.

Static page controller for the Task Console demo.
"""

from __future__ import annotations

from pathlib import Path

from starlette.requests import Request

from quadkit.web import Controller, FileResponse, get

ROOT = Path(__file__).resolve().parent
SHARED_ASSETS = ROOT.parent.parent.parent.parent / "shared" / "assets"


# tokens.css/theme-toggle.js are shared across the whole fleet and can
# change independently of any single demo's deploy (e.g. a brand-accent
# revision) — force revalidation so a stale browser cache never keeps
# serving an old palette after the file changes on disk.
NO_CACHE_HEADERS = {"Cache-Control": "no-cache"}


class TaskConsolePageController(Controller):
    """Serve the no-build browser console."""

    @get("/")
    async def console(self, request: Request) -> FileResponse:
        return FileResponse(ROOT / "views/console.html", media_type="text/html")

    @get("/static/style.css")
    async def stylesheet(self, request: Request) -> FileResponse:
        return FileResponse(ROOT / "static/style.css", media_type="text/css")

    @get("/static/app.js")
    async def app_js(self, request: Request) -> FileResponse:
        return FileResponse(ROOT / "static/app.js", media_type="text/javascript")

    @get("/static/logo.png")
    async def logo(self, request: Request) -> FileResponse:
        """Shared brand logo (canonical asset)."""
        return FileResponse(SHARED_ASSETS / "logo.png", media_type="image/png")

    @get("/static/icon.png")
    async def icon(self, request: Request) -> FileResponse:
        """Shared favicon (canonical asset)."""
        return FileResponse(SHARED_ASSETS / "icon.png", media_type="image/png")

    @get("/static/tokens.css")
    async def tokens_css(self, request: Request) -> FileResponse:
        """Shared design tokens (canonical colors, light/dark palettes)."""
        return FileResponse(
            SHARED_ASSETS / "tokens.css",
            media_type="text/css",
            headers=NO_CACHE_HEADERS,
        )

    @get("/static/theme-toggle.js")
    async def theme_toggle_js(self, request: Request) -> FileResponse:
        """Shared light/dark theme toggle script."""
        return FileResponse(
            SHARED_ASSETS / "theme-toggle.js",
            media_type="text/javascript",
            headers=NO_CACHE_HEADERS,
        )


__all__ = ["TaskConsolePageController"]
