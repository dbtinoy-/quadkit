"""Stacking route decorators declares an alias, not a silent 404.

One handler often serves two paths: a legacy URL kept alive beside its
replacement, or a prefixed twin. Writing that is the obvious thing —

    @get("/openapi.json")
    @get("/api/v1/openapi.json")
    async def spec(self): ...

— and it used to produce exactly one route. The decorator assigned a
single ``_route_config``, so the outer one overwrote the inner, and the
other path simply did not exist: no error, no warning, a 404 at runtime
for a route the source plainly declares. Three such routes had been
missing from qk-erp since the day they were written.
"""

from __future__ import annotations

from quadkit.web.routing.controllers import Controller
from quadkit.web.routing.decorators import get, post


class _Aliased(Controller):
    """A controller whose handlers each serve more than one path."""

    prefix = ""

    @get("/openapi.json")
    @get("/api/v1/openapi.json")
    async def spec(self) -> dict[str, str]:
        return {}

    @post("/jsonrpc")
    @post("/web/dataset/call_kw")
    async def call(self) -> dict[str, str]:
        return {}

    @get("/plain")
    async def plain(self) -> dict[str, str]:
        return {}


def _routes() -> list[tuple[str, str, str]]:
    collected = _Aliased.collect_routes()
    return [(r["method"], r["path"], r["handler_name"]) for r in collected]


def test_every_stacked_path_registers() -> None:
    routes = _routes()
    assert ("GET", "/openapi.json", "spec") in routes
    assert ("GET", "/api/v1/openapi.json", "spec") in routes
    assert ("POST", "/jsonrpc", "call") in routes
    assert ("POST", "/web/dataset/call_kw", "call") in routes


def test_paths_keep_the_order_they_were_written_in() -> None:
    """Decorators apply bottom-up; the reader expects top-down."""
    spec_paths = [path for method, path, handler in _routes() if handler == "spec"]
    assert spec_paths == ["/openapi.json", "/api/v1/openapi.json"]


def test_a_single_decorator_is_unaffected() -> None:
    assert ("GET", "/plain", "plain") in _routes()
    assert len([r for r in _routes() if r[2] == "plain"]) == 1


def test_the_last_config_is_still_exposed_singly() -> None:
    """The docs decorators merge metadata into ``_route_config``."""
    assert _Aliased.spec._route_config["path"] == "/openapi.json"
    assert len(_Aliased.spec._route_configs) == 2
