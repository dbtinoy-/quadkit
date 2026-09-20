"""Web fixtures and the module surfaces around TestEnvironment."""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

from quadkit.testing.fixtures import containers as containers_mod
from quadkit.testing.fixtures.containers import (
    ContainerFactory,
)
from quadkit.testing.fixtures.web import (
    app_bed,
    authenticated_web_client,
    mock_web_request,
    mock_web_response,
    sample_web_post_data,
    sample_web_user_data,
    web_test_bed,
    web_test_client,
)

# ---------------------------------------------------------------------------
# fixtures/web.py
# ---------------------------------------------------------------------------


def test_web_sync_fixtures() -> None:
    client = web_test_client.__wrapped__()
    assert client is not None

    request = mock_web_request.__wrapped__()
    assert request.method == "GET"
    assert request.headers["Content-Type"] == "application/json"
    assert request.query_params == {}

    response = mock_web_response.__wrapped__()
    assert response.status_code == 200

    user = sample_web_user_data.__wrapped__()
    assert user["username"] == "testuser"
    post = sample_web_post_data.__wrapped__()
    assert post["title"] == "Test Post"


async def test_web_test_bed_fixture() -> None:
    gen = web_test_bed.__wrapped__()
    bed = await gen.__anext__()
    try:
        assert bed.app is not None
        assert bed.client is not None
    finally:
        await gen.aclose()


async def test_authenticated_web_client_fixture() -> None:
    client = web_test_client.__wrapped__()
    # Return-style async fixture → plain coroutine, not a generator.
    result = await authenticated_web_client.__wrapped__(client)
    assert result is client


async def test_app_bed_no_entry_point() -> None:
    from quadkit.cli.registry import server as server_mod

    original = server_mod.discover_entry_point
    server_mod.discover_entry_point = lambda: None
    try:
        gen = app_bed.__wrapped__()
        value = await gen.__anext__()
        await gen.aclose()
        assert value is None
    finally:
        server_mod.discover_entry_point = original


async def test_app_bed_discovers_create_app(tmp_path: Any, monkeypatch: Any) -> None:
    from quadkit.cli.registry import server as server_mod

    src = tmp_path / "src" / "demo_app"
    src.mkdir(parents=True)
    app_file = src / "app.py"
    app_file.write_text(
        "from quadkit.app.base import Application\n\n"
        "def create_app() -> Application:\n"
        "    return Application(name='discovered-app')\n",
        encoding="utf-8",
    )

    original = server_mod.discover_entry_point
    # app_bed converts relative paths rooted at "src" into dotted modules,
    # so the entry point must be discovered relative to the tmp root.
    server_mod.discover_entry_point = lambda: "src/demo_app/app.py"
    # module path strips "src" → demo_app must be importable from tmp/src
    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    monkeypatch.chdir(tmp_path)
    try:
        gen = app_bed.__wrapped__()
        bed = await gen.__anext__()
        assert bed is not None
        assert bed.app.name == "discovered-app"
        await gen.aclose()
    finally:
        server_mod.discover_entry_point = original
        sys.modules.pop("demo_app.app", None)


async def test_app_bed_no_create_app_function(tmp_path: Any) -> None:
    from quadkit.cli.registry import server as server_mod

    src = tmp_path / "src" / "other_app"
    src.mkdir(parents=True)
    app_file = src / "app.py"
    app_file.write_text("VALUE = 1\n", encoding="utf-8")

    original = server_mod.discover_entry_point
    server_mod.discover_entry_point = lambda: str(app_file)
    try:
        gen = app_bed.__wrapped__()
        value = await gen.__anext__()
        await gen.aclose()
        assert value is None
    finally:
        server_mod.discover_entry_point = original


# ---------------------------------------------------------------------------
# ast sanity: app_bed parses real module source
# ---------------------------------------------------------------------------


def test_ast_function_detection_helper() -> None:
    source = "def create_app():\n    return 1\n"
    tree = ast.parse(source)
    found = [
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert found == ["create_app"]
    assert Path("src/x/app.py").with_suffix("") == Path("src/x/app")


# ---------------------------------------------------------------------------
# containers module surface
# ---------------------------------------------------------------------------


def test_containers_all_exports() -> None:
    assert containers_mod.__all__ == [
        "ContainerFactory",
        "apply_overrides",
        "rebind_overrides",
    ]
    factory = ContainerFactory()
    assert "DatabaseProviderProtocol" in factory._common_protocols
    assert "StateStoreProtocol" in factory._common_protocols
