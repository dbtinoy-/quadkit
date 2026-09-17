"""Feature tour: static files — assets as configuration, not plumbing.

Serving a directory is a config decision, so that is where it lives:
``WebConfig(static=StaticFileConfig(enabled=True, directory=...,
prefix=...))`` mounts the assets tree at boot — content types come from
file extensions, nested paths work, and requests that miss the tree or
try to escape ``directory`` get plain 404s, with path traversal refused
inside the filesystem layer rather than by string filtering.
``html=True`` upgrades the mount into SPA mode, where a directory
request serves its ``index.html``.
"""

import pathlib

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import WebModule
from quadkit.web.config.api_docs import StaticFileConfig
from quadkit.web.config.top_level import WebConfig


def make_app(assets: pathlib.Path, *, html: bool = False) -> Application:
    app = Application()
    app.add_module(
        WebModule.configure(
            controllers=[],
            web_config=WebConfig(
                static=StaticFileConfig(
                    enabled=True, directory=str(assets), prefix="/assets", html=html
                )
            ),
        )
    )
    return app


@pytest.fixture
def assets(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "public"
    root.mkdir()
    (root / "app.css").write_text("body{color:teal}\n")
    img = root / "img"
    img.mkdir()
    (img / "logo.txt").write_text("logo-bytes")
    (root / "index.html").write_text("<h1>cuadro</h1>")
    return root


@pytest.mark.asyncio
async def test_assets_serve_with_content_types(assets: pathlib.Path) -> None:
    async with WebTestBed(make_app(assets)) as bed:
        css = bed.get("/assets/app.css")
        assert css.status_code == 200
        assert css.headers["content-type"].startswith("text/css")
        assert css.text == "body{color:teal}\n"

        # Nested paths resolve beneath the mount.
        logo = bed.get("/assets/img/logo.txt")
        assert logo.status_code == 200
        assert logo.text == "logo-bytes"


@pytest.mark.asyncio
async def test_missing_and_traversal_are_plain_404s(assets: pathlib.Path) -> None:
    async with WebTestBed(make_app(assets)) as bed:
        assert bed.get("/assets/does-not-exist.css").status_code == 404
        assert bed.get("/assets/../pyproject.toml").status_code == 404
        assert bed.get("/assets/%2e%2e/pyproject.toml").status_code == 404


@pytest.mark.asyncio
async def test_html_mode_serves_index_for_directories(assets: pathlib.Path) -> None:
    async with WebTestBed(make_app(assets, html=True)) as bed:
        page = bed.get("/assets/")
        assert page.status_code == 200
        assert "<h1>cuadro</h1>" in page.text
        assert page.headers["content-type"].startswith("text/html")
