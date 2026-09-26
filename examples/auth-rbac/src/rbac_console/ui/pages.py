"""Convention followed: **Page controller pattern** — static-only serving of views plus shared brand assets.

Server-rendered pages + static assets for the RBAC console.

Demonstrates the *page controller* half of a Quadkit web app: HTML lives
in ``ui/views/``, assets in ``ui/static/``, and this controller serves
them with zero business logic — every dynamic interaction goes through
the JSON API in ``controllers/api.py`` instead.  HTMX/vanilla-JS in the
views calls those endpoints directly.
"""

from __future__ import annotations

from pathlib import Path

from starlette.requests import Request

from quadkit.web import Controller, FileResponse, RedirectResponse, get

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
    return FileResponse(path=VIEWS_ROOT / name, media_type="text/html")


def _static(name: str, media_type: str) -> FileResponse:
    return FileResponse(path=STATIC_ROOT / name, media_type=media_type)


class PagesController(Controller):
    """Serve the console's HTML/JS/CSS; logic lives in the API controller.

    Quadkit convention: page controllers are stateless — they serve
    files and redirect, nothing more.  All dynamic behavior goes through
    the JSON API (RbacApiController).  HTMX/vanilla-JS in the views
    calls those endpoints directly.

    If you use an external frontend (React, Vue), omit this controller
    entirely — RbacApiController is all you need.
    """

    def __init__(self) -> None:
        """Stateless: no constructor dependencies needed."""

    @get("/")
    async def index(self, request: Request) -> RedirectResponse:
        """Redirect root to /matrix — convention: root serves the main view."""
        return RedirectResponse(url="/matrix", status_code=307)

    @get("/login")
    async def login_page(self, request: Request) -> FileResponse:
        return _view("login.html")

    @get("/matrix")
    async def matrix_page(self, request: Request) -> FileResponse:
        # The JS client calls /api/me and redirects to /login on 401.
        return _view("matrix.html")

    @get("/static/style.css")
    async def stylesheet(self, request: Request) -> FileResponse:
        return _static("style.css", "text/css")

    @get("/static/app.js")
    async def app_js(self, request: Request) -> FileResponse:
        return _static("app.js", "text/javascript")

    @get("/static/matrix.js")
    async def matrix_js(self, request: Request) -> FileResponse:
        return _static("matrix.js", "text/javascript")

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


__all__ = ["PagesController"]
