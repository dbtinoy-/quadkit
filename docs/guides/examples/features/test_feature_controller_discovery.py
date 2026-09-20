"""Feature tour: controller discovery — point at a package, routes appear.

`discover_controllers(("myapp.controllers",))` walks the package tree,
imports every module, and returns the concrete `Controller` subclasses
it finds — deduplicated, helpers and non-controllers ignored, classes
not instances (the DI container constructs them during boot). Hand the
list straight to `WebModule.configure(controllers=...)` and convention
replaces registration boilerplate.
"""

import textwrap
from collections.abc import Iterator

import pytest

from quadkit import Application
from quadkit.testing import WebTestBed
from quadkit.web import Controller, WebModule, discover_controllers


@pytest.fixture
def shop_package(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A hermetic `shop` package with two controllers and one decoy."""
    pkg = tmp_path / "shop"
    (pkg / "admin").mkdir(parents=True)
    (pkg / "metrics").mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "admin" / "__init__.py").write_text(
        textwrap.dedent(
            '''
            from quadkit.web import Controller, get


            class AdminController(Controller):
                @get("/admin/health")
                async def health(self) -> dict:
                    return {"ok": True}
            '''
        )
    )
    (pkg / "metrics" / "__init__.py").write_text(
        textwrap.dedent(
            '''
            from quadkit.web import Controller, get


            class MetricsController(Controller):
                @get("/metrics/ping")
                async def ping(self) -> dict:
                    return {"pong": True}
            '''
        )
    )
    # A submodule that must NOT be discovered: helper + non-Controller class.
    (pkg / "helpers.py").write_text(
        textwrap.dedent(
            '''
            def helper() -> str:
                return "not a controller"


            class PlainOldClass:
                pass
            '''
        )
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    yield "shop"


def test_discovery_walks_packages_and_keeps_controllers_only(
    shop_package: str,
) -> None:
    found = discover_controllers([shop_package])

    names = sorted(cls.__name__ for cls in found)
    assert names == ["AdminController", "MetricsController"]
    assert all(issubclass(cls, Controller) for cls in found)

    # Missing packages are a quiet no-op, not an import-time crash.
    assert discover_controllers(["shop.does_not_exist"]) == []


@pytest.mark.asyncio
async def test_discovered_controllers_serve_their_routes(shop_package: str) -> None:
    controllers = discover_controllers([shop_package])

    app = Application()
    app.add_module(WebModule.configure(controllers=controllers))
    async with WebTestBed(app) as bed:
        assert bed.get("/admin/health").json == {"ok": True}
        assert bed.get("/metrics/ping").json == {"pong": True}
        assert bed.get("/helpers").status_code == 404  # decoy served nothing
