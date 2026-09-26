"""Convention followed: **Page controller pattern** — static-only serving of views plus shared brand assets.

Order console page — static serving only (logic lives in the API controller).

Convention: page controllers serve static HTML/CSS/JS assets.  They contain
no business logic — all dynamic behavior comes from the API controller's
endpoints.  The page controller is registered alongside the API controller
in the composition root's ``WebModule.configure(controllers=[...])``.
"""

from __future__ import annotations

from pathlib import Path

from starlette.requests import Request

from quadkit.web import Controller, FileResponse, get

UI_ROOT = Path(__file__).resolve().parent
VIEWS_ROOT = UI_ROOT / "views"
STATIC_ROOT = UI_ROOT / "static"
SHARED_ASSETS = UI_ROOT.parent.parent.parent.parent / "shared" / "assets"


# tokens.css/theme-toggle.js are shared across the whole fleet and can
# change independently of any single demo's deploy (e.g. a brand-accent
# revision) — force revalidation so a stale browser cache never keeps
# serving an old palette after the file changes on disk.
NO_CACHE_HEADERS = {"Cache-Control": "no-cache"}


def _view(name: str) -> FileResponse:
    """Serve one HTML view."""
    return FileResponse(path=VIEWS_ROOT / name, media_type="text/html")


def _static(name: str, media_type: str) -> FileResponse:
    """Serve one static asset."""
    return FileResponse(path=STATIC_ROOT / name, media_type=media_type)


class OrdersPageController(Controller):
    """Serve the order console; every handler reads from ui/.

    Convention: page controllers are stateless — no constructor
    injection, no business logic.  They exist only to map routes
    to files.
    """

    def __init__(self) -> None:
        """Stateless."""

    @get("/")
    async def console(self, request: Request) -> FileResponse:
        """The single-page console."""
        return _view("console.html")

    @get("/static/style.css")
    async def stylesheet(self, request: Request) -> FileResponse:
        return _static("style.css", "text/css")

    @get("/static/app.js")
    async def app_js(self, request: Request) -> FileResponse:
        return _static("app.js", "text/javascript")

    @get("/static/logo.png")
    async def logo(self, request: Request) -> FileResponse:
        return FileResponse(path=SHARED_ASSETS / "logo.png", media_type="image/png")

    @get("/static/icon.png")
    async def icon(self, request: Request) -> FileResponse:
        return FileResponse(path=SHARED_ASSETS / "icon.png", media_type="image/png")

    @get("/static/tokens.css")
    async def tokens_css(self, request: Request) -> FileResponse:
        """Shared design tokens (canonical colors, light/dark palettes)."""
        return FileResponse(
            path=SHARED_ASSETS / "tokens.css",
            media_type="text/css",
            headers=NO_CACHE_HEADERS,
        )

    @get("/static/theme-toggle.js")
    async def theme_toggle_js(self, request: Request) -> FileResponse:
        """Shared light/dark theme toggle script."""
        return FileResponse(
            path=SHARED_ASSETS / "theme-toggle.js",
            media_type="text/javascript",
            headers=NO_CACHE_HEADERS,
        )


__all__ = ["OrdersPageController"]
