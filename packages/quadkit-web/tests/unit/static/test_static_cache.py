import os
import tempfile

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from quadkit.web.middleware.static import StaticFilesMiddleware


def _make_app(directory: str, **kwargs):
    inner = Starlette(routes=[Route("/other", lambda _: PlainTextResponse("home"))])
    return StaticFilesMiddleware(inner, directory=directory, prefix="/static", **kwargs)


def _dummy_asset(td: str) -> None:
    with open(os.path.join(td, "asset.txt"), "w") as fh:
        fh.write("ok")


def test_static_default_cache_is_one_year():
    with tempfile.TemporaryDirectory() as td:
        _dummy_asset(td)
        with TestClient(_make_app(td)) as client:
            response = client.get("/static/asset.txt")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "public, max-age=31536000"


def test_static_cache_max_age_override():
    with tempfile.TemporaryDirectory() as td:
        _dummy_asset(td)
        with TestClient(_make_app(td, cache_max_age=0)) as client:
            response = client.get("/static/asset.txt")
            assert response.status_code == 200
            assert response.headers["cache-control"] == "public, max-age=0"


@pytest.mark.parametrize("cache_max_age", [0, 31536000])
def test_static_cache_header_not_applied_outside_prefix(cache_max_age):
    with tempfile.TemporaryDirectory() as td:
        _dummy_asset(td)
        with TestClient(_make_app(td, cache_max_age=cache_max_age)) as client:
            response = client.get("/other")
            assert response.status_code == 200
            assert "cache-control" not in response.headers
