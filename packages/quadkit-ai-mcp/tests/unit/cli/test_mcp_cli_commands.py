"""Unit tests for the MCP CLI serve command (cli/commands.py).

Covers entry-point discovery helpers, entry-point resolution, app
loading, the stdio transport loop, loopback-origin logic, script-mode
routing, and the non-loopback SSE binding warning.

The SSE HTTP handler itself is covered in test_mcp_sse_origin_policy.py.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any

import pytest
from typer import Exit as TyperExit

from quadkit.ai.mcp import cli
from quadkit.ai.mcp.cli import commands
import quadkit.serialization as json

# ---------------------------------------------------------------------------
# Entry-point discovery helpers
# ---------------------------------------------------------------------------


class TestPathToModule:
    def test_path_shapes(self) -> None:
        assert commands._path_to_module("src/main.py") == "main"
        assert commands._path_to_module("main.py") == "main"
        assert commands._path_to_module("my_app/app.py") == "my_app.app"

    def test_dot_prefixed_relative_path(self) -> None:
        """'./' prefixes must not leak a leading dot into the module
        string (an invalid relative import name)."""
        assert commands._path_to_module("./main.py") == "main"
        assert commands._path_to_module("./src/app.py") == "app"
        assert commands._path_to_module("./my_app/tools.py") == "my_app.tools"

    def test_absolute_path_no_leading_slash_dot(self) -> None:
        """Path.parts of an absolute path starts with '/', which would
        join into a leading-slash/dot module name — an invalid import."""
        assert (
            commands._path_to_module("/home/user/proj/main.py") == "home.user.proj.main"
        )


class TestDetectFactoryAttr:
    def test_precedence_and_shapes(self, tmp_path: Any) -> None:
        p = tmp_path / "a.py"
        p.write_text("def create_app():\n    return 1\n\napp = object()\n")
        assert commands._detect_factory_attr(str(p)) == "create_app"

        p = tmp_path / "b.py"
        p.write_text("asgi_app = object()\n")
        assert commands._detect_factory_attr(str(p)) == "asgi_app"

        p = tmp_path / "c.py"
        p.write_text("async def create_app():\n    return 1\n")
        assert commands._detect_factory_attr(str(p)) == "create_app"

        p = tmp_path / "d.py"
        p.write_text("def other():\n    return 1\n")
        assert commands._detect_factory_attr(str(p)) is None

    def test_unparseable_returns_none(self, tmp_path: Any) -> None:
        p = tmp_path / "bad.py"
        p.write_text("def broken(:\n")
        assert commands._detect_factory_attr(str(p)) is None


class TestDiscoverEntryPoint:
    def test_candidate_order(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Discovery is existence-based — the factory check happens in
        # _resolve_entry_point, not here.
        monkeypatch.chdir(tmp_path)
        assert commands._discover_entry_point() is None

        (tmp_path / "app.py").write_text("app = 1\n")
        assert commands._discover_entry_point() == "app.py"

        # main.py outranks app.py in the candidate order
        (tmp_path / "main.py").write_text("def create_app(): pass\n")
        assert commands._discover_entry_point() == "main.py"

    def test_src_subtree(self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def create_app(): pass\n")

        assert commands._discover_entry_point() == str(Path("src") / "main.py")


class TestResolveEntryPoint:
    def test_explicit_module_attr_passthrough(self) -> None:
        assert (
            commands._resolve_entry_point("my_app.app:create_app")
            == "my_app.app:create_app"
        )

    def test_no_entry_point_exits(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)

        with pytest.raises(TyperExit):
            commands._resolve_entry_point(None)

    def test_no_factory_exits(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "main.py").write_text("def unrelated(): pass\n")

        with pytest.raises(TyperExit):
            commands._resolve_entry_point("main.py")

    def test_detected_entry_point(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        (tmp_path / "main.py").write_text("def create_app(): pass\n")

        assert commands._resolve_entry_point("main.py") == "main:create_app"


class TestLoadApp:
    def test_factory_called_and_instance_returned(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "tmpmod_r73.py").write_text(
            "def make_app():\n    return 'APP'\nSTATIC = 'STATIC'\n"
        )
        monkeypatch.syspath_prepend(str(tmp_path))
        try:
            assert commands._load_app("tmpmod_r73:make_app") == "APP"
            assert commands._load_app("tmpmod_r73:STATIC") == "STATIC"
        finally:
            sys.modules.pop("tmpmod_r73", None)

    def test_missing_module_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            commands._load_app("no_such_module_r73:app")


# ---------------------------------------------------------------------------
# Loopback origin
# ---------------------------------------------------------------------------


class TestIsLoopbackOrigin:
    @pytest.mark.parametrize(
        ("origin", "expected"),
        [
            ("http://127.0.0.1:3000", True),
            ("http://localhost:8080", True),
            ("http://[::1]:9000", True),
            ("http://127.0.0.1", True),
            ("http://evil.com", False),
            ("http://127.0.0.2", False),
            ("http://localhost.evil.com", False),
        ],
    )
    def test_variants(self, origin: str, expected: bool) -> None:
        assert commands._is_loopback_origin(origin) is expected

    def test_malformed_origin(self) -> None:
        assert commands._is_loopback_origin("://bad") is False


# ---------------------------------------------------------------------------
# Script-mode helpers
# ---------------------------------------------------------------------------


class TestIsScriptTarget:
    def test_shapes(self, tmp_path: Any) -> None:
        # .py paths are always script mode by design (docstring);
        # the factory check only applies to extensionless existing files
        assert commands._is_script_target("tools.py") is True
        assert commands._is_script_target("my_app.app:create_app") is False
        assert commands._is_script_target("my_app.mcp_tools") is True
        app = tmp_path / "entry"  # extensionless file
        app.write_text("def create_app(): pass\n")
        assert commands._is_script_target(str(app)) is False


class TestLoadScriptModule:
    def test_file_and_dotted(self, tmp_path: Any) -> None:
        path = tmp_path / "script_r73.py"
        path.write_text("VALUE = 42\n")

        mod = commands._load_script_module(str(path))
        assert mod.VALUE == 42

        assert commands._load_script_module("os") is sys.modules["os"]


class TestBuildScriptServer:
    def test_name_version_and_roundtrip(self, tmp_path: Any) -> None:
        path = tmp_path / "tools_r73.py"
        path.write_text(
            "from quadkit.ai.mcp.controllers.decorators import tool\n"
            "\n"
            "__mcp_name__ = 'my-tools'\n"
            "__mcp_version__ = '2.0.0'\n"
            "\n"
            '@tool("echo", description="echoes input")\n'
            "def echo(text: str = '') -> str:\n"
            "    return text\n"
        )

        mod = commands._load_script_module(str(path))
        server = commands._build_script_server(mod)

        assert server._name == "my-tools"
        assert server._version == "2.0.0"

        # protocol handshake first, then list tools
        init = asyncio.run(
            server.handle_message(
                {
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "id": 1,
                    "params": {"clientInfo": {"name": "test"}},
                }
            )
        )
        # MCP wire format: capabilities are name -> {} maps
        caps = init["result"]["capabilities"]
        assert set(caps) == {"tools", "resources", "prompts"}

        response = asyncio.run(
            server.handle_message({"jsonrpc": "2.0", "method": "tools/list", "id": 2})
        )
        assert response["id"] == 2
        names = [t["name"] for t in response["result"]["tools"]]
        assert "echo" in names


# ---------------------------------------------------------------------------
# stdio transport
# ---------------------------------------------------------------------------


class TestServeStdio:
    @pytest.mark.asyncio
    async def test_roundtrip_skips_invalid_and_exits_on_eof(self, capsys: Any) -> None:
        class _Srv:
            def __init__(self) -> None:
                self.messages: list[dict[str, Any]] = []

            async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
                self.messages.append(message)
                return {
                    "jsonrpc": "2.0",
                    "result": "ok",
                    "id": message.get("id"),
                }

        srv = _Srv()
        closed: list[bool] = []

        loop = asyncio.get_running_loop()

        async def fake_connect_read_pipe(protocol_factory: Any, file: Any) -> Any:
            proto = protocol_factory()
            proto._stream_reader.feed_data(  # CPython-internal, stable
                b'{"jsonrpc":"2.0","method":"ping","id":1}\nnot-json\n\n'
            )
            proto._stream_reader.feed_eof()
            return SimpleNamespace(close=lambda: closed.append(True)), None

        loop.connect_read_pipe = fake_connect_read_pipe  # type: ignore[method-assign]

        await commands._serve_stdio(srv)

        assert srv.messages == [{"jsonrpc": "2.0", "method": "ping", "id": 1}]
        out = capsys.readouterr().out.strip()
        assert json.loads(out)["result"] == "ok"
        assert closed == [True]


# ---------------------------------------------------------------------------
# serve() command
# ---------------------------------------------------------------------------


def _write_tools(tmp_path: Any) -> str:
    path = tmp_path / "tools.py"
    path.write_text(
        "from quadkit.ai.mcp.controllers.decorators import tool\n"
        "\n"
        '@tool("echo", description="echoes input")\n'
        "def echo(text: str = '') -> str:\n"
        "    return text\n"
    )
    return str(path)


class TestServeCommand:
    def test_unknown_transport_exits(self, tmp_path: Any, capsys: Any) -> None:
        target = _write_tools(tmp_path)

        with pytest.raises(TyperExit):
            cli.commands.serve(target, transport="carrier-pigeon")

        assert "Unknown transport" in capsys.readouterr().err

    def test_script_mode_sse_routing(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        target = _write_tools(tmp_path)
        calls: list[tuple[object, str, int]] = []

        async def fake_sse(server: object, host: str, port: int) -> None:
            calls.append((server, host, port))

        monkeypatch.setattr(commands, "_serve_sse", fake_sse)

        commands.serve(target, transport="sse", host="127.0.0.1", port=9123)

        assert len(calls) == 1
        server, host, port = calls[0]
        assert host == "127.0.0.1"
        assert port == 9123
        assert type(server).__name__ == "MCPServer"
        assert "Script mode: loading" in capsys.readouterr().err

    def test_non_loopback_sse_warns(
        self, tmp_path: Any, monkeypatch: pytest.MonkeyPatch, capsys: Any
    ) -> None:
        target = _write_tools(tmp_path)

        async def fake_sse(server: object, host: str, port: int) -> None:
            pass

        monkeypatch.setattr(commands, "_serve_sse", fake_sse)

        commands.serve(target, transport="sse", host="0.0.0.0", port=9124)

        assert "non-loopback" in capsys.readouterr().err

    def test_profile_sets_env(
        self,
        tmp_path: Any,
        monkeypatch: pytest.MonkeyPatch,
        capsys: Any,
    ) -> None:
        target = _write_tools(tmp_path)

        async def fake_sse(server: object, host: str, port: int) -> None:
            pass

        monkeypatch.setattr(commands, "_serve_sse", fake_sse)
        monkeypatch.delenv("QK_PROFILE", raising=False)

        try:
            commands.serve(
                target,
                transport="sse",
                host="127.0.0.1",
                port=9125,
                profile="prod",
            )
            assert os.environ["QK_PROFILE"] == "prod"
        finally:
            os.environ.pop("QK_PROFILE", None)
