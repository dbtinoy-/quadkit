"""Feature tour: server-rendered templates.

`Jinja2Templates` is a constructor-injected engine — register it as a
container singleton, inject it into controllers, inherit context processors
and autoescaping. `render_template(...)` renders to a string (compose with
`html_response`). The example deliberately demos the security default:
`{{ user_html }}` is autoescaped.
"""

from pathlib import Path

import pytest
from starlette.requests import Request

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, get, html_response
from quadkit.web.templates.core import Jinja2Templates

TEMPLATE_DIR: Path | None = None


def version_processor(context: dict) -> dict:
    """Context processor: every template sees the app version."""
    context["app_version"] = "2.1.0"
    return context


class PageController(Controller):
    prefix = "/profile"

    @get("")
    async def profile(self, request: Request) -> object:
        engine = Jinja2Templates(
            directory=TEMPLATE_DIR,
            context_processors=[version_processor],
        )
        markup = engine.render_template(
            "profile.html",
            {
                "name": request.query_params.get("name", "quadkiter"),
                "untrusted": request.query_params.get("untrusted", "ok"),
            },
        )
        return html_response(markup)


PROFILE_HTML = """\
<!doctype html>
<title>profile of {{ name }}</title>
<h1>hello {{ name }}</h1>
<p>running quadkit {{ app_version }}</p>
<pre>{{ untrusted }}</pre>
"""


def create_app(directory: Path) -> Application:
    global TEMPLATE_DIR
    TEMPLATE_DIR = directory
    app = Application()
    app.add_module(WebModule.configure(controllers=[PageController]))
    return app


@pytest.mark.asyncio
async def test_rendered_template_binds_processors_and_autoescapes(tmp_path: Path) -> None:
    (tmp_path / "profile.html").write_text(PROFILE_HTML)

    async with WebTestBed(create_app(tmp_path)) as bed:
        response = bed.get(
            "/profile",
            params={"name": "ada", "untrusted": "<script>alert(1)</script>"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/html; charset=utf-8"
        body = response.text
        assert "<title>profile of ada</title>" in body
        assert "running quadkit 2.1.0" in body  # context processor ran
        assert "<script>alert(1)</script>" not in body  # autoescaped
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body

        # Render to string without a route (unit flavour).
        engine = Jinja2Templates(directory=tmp_path, context_processors=[version_processor])
        rendered = engine.render_template("profile.html", {"name": "grace"})
        assert "<h1>hello grace</h1>" in rendered
        assert "quadkit 2.1.0" in rendered  # processors apply here too
