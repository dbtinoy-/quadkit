"""Tests for server runner module."""

from __future__ import annotations

import sys
import threading
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class _FakeUvicorn:
    """Minimal uvicorn stand-in that records configs and serves immediately."""

    def __init__(self) -> None:
        self.configs: list[object] = []

    class Config:
        def __init__(self, app: object, host: str, port: int, **kwargs: object) -> None:
            self.app = app
            self.host = host
            self.port = port
            self.kwargs = kwargs

    class Server:
        def __init__(self, config: object) -> None:
            self.config = config

        async def serve(self) -> None:
            pass

    def make_module(self) -> Any:
        return SimpleNamespace(Config=self._record, Server=_FakeUvicorn.Server)

    def _record(self, app: object, host: str, port: int, **kwargs: object) -> object:
        config = _FakeUvicorn.Config(app, host, port, **kwargs)
        self.configs.append(config)
        return config


class TestRunServer:
    """Test suite for run_server function."""

    def test_creates_granian_with_correct_parameters(self) -> None:
        """String app: run_server creates Granian with correct parameters."""
        mock_granian_cls = MagicMock()
        mock_granian_instance = MagicMock()
        mock_granian_cls.return_value = mock_granian_instance
        mock_interfaces = MagicMock()
        mock_interfaces.ASGI = "asgi"

        mock_granian_module = MagicMock()
        mock_granian_module.Granian = mock_granian_cls
        mock_constants_module = MagicMock()
        mock_constants_module.Interfaces = mock_interfaces

        with patch.dict(
            "sys.modules",
            {
                "granian": mock_granian_module,
                "granian.constants": mock_constants_module,
            },
        ):
            from quadkit.web.server.runner import run_server

            run_server("module:app", host="127.0.0.1", port=9000, workers=2)

        mock_granian_cls.assert_called_once()
        call_args = mock_granian_cls.call_args
        assert call_args[0][0] == "module:app"
        assert call_args[1]["address"] == "127.0.0.1"
        assert call_args[1]["port"] == 9000
        assert call_args[1]["interface"] == "asgi"
        assert call_args[1]["workers"] == 2

        mock_granian_instance.serve.assert_called_once()

    def test_uses_default_host_and_port(self) -> None:
        """String app: run_server uses default host and port when not specified."""
        mock_granian_cls = MagicMock()
        mock_granian_instance = MagicMock()
        mock_granian_cls.return_value = mock_granian_instance
        mock_interfaces = MagicMock()
        mock_interfaces.ASGI = "asgi"

        mock_granian_module = MagicMock()
        mock_granian_module.Granian = mock_granian_cls
        mock_constants_module = MagicMock()
        mock_constants_module.Interfaces = mock_interfaces

        with patch.dict(
            "sys.modules",
            {
                "granian": mock_granian_module,
                "granian.constants": mock_constants_module,
            },
        ):
            from quadkit.web.server.runner import run_server

            run_server("module:app")

        call_args = mock_granian_cls.call_args
        assert call_args[1]["address"] == "127.0.0.1"
        assert call_args[1]["port"] == 8000

    def test_passes_extra_kwargs_to_granian(self) -> None:
        """String app: run_server passes additional kwargs to Granian."""
        mock_granian_cls = MagicMock()
        mock_granian_instance = MagicMock()
        mock_granian_cls.return_value = mock_granian_instance
        mock_interfaces = MagicMock()
        mock_interfaces.ASGI = "asgi"

        mock_granian_module = MagicMock()
        mock_granian_module.Granian = mock_granian_cls
        mock_constants_module = MagicMock()
        mock_constants_module.Interfaces = mock_interfaces

        with patch.dict(
            "sys.modules",
            {
                "granian": mock_granian_module,
                "granian.constants": mock_constants_module,
            },
        ):
            from quadkit.web.server.runner import run_server

            run_server("module:app", host="0.0.0.0", port=8080, reload=True, workers=4)

        call_args = mock_granian_cls.call_args
        assert call_args[1]["reload"] is True
        assert call_args[1]["workers"] == 4

    def test_falls_back_to_uvicorn_when_granian_unavailable(self) -> None:
        """String app: run_server falls back to Uvicorn when Granian is unavailable."""
        granian_modules = [k for k in sys.modules if k.startswith("granian")]
        removed = {k: sys.modules.pop(k) for k in granian_modules}

        fake_uvicorn = _FakeUvicorn()

        try:
            with patch.dict("sys.modules", {"granian": None, "granian.constants": None, "uvicorn": fake_uvicorn.make_module()}):
                from quadkit.web.server.runner import run_server

                run_server("module:app", host="127.0.0.1", port=9000)
        finally:
            sys.modules.update(removed)

        assert len(fake_uvicorn.configs) == 1
        config = fake_uvicorn.configs[0]
        assert config.app == "module:app"
        assert config.host == "127.0.0.1"
        assert config.port == 9000

    def test_instance_uses_uvicorn(self) -> None:
        """App instance: run_server delegates to Uvicorn when Granian unavailable."""
        mock_app = MagicMock()
        fake_uvicorn = _FakeUvicorn()

        def _run() -> None:
            with patch.dict(
                "sys.modules",
                {"uvicorn": fake_uvicorn.make_module(), "granian": None, "granian.constants": None},
            ):
                from quadkit.web.server.runner import run_server

                run_server(mock_app, host="0.0.0.0", port=8080, workers=2)

        thread = threading.Thread(target=_run)
        thread.start()
        thread.join()

        assert len(fake_uvicorn.configs) == 1
        config = fake_uvicorn.configs[0]
        assert config.app is mock_app
        assert config.host == "0.0.0.0"
        assert config.port == 8080
        # workers is runner-managed since 2026-10-24: popped before
        # dispatch (and warned about — in-process Uvicorn cannot honour
        # it), never forwarded raw into uvicorn.Config.
        assert config.kwargs == {}

    def test_instance_uses_default_host_and_port(self) -> None:
        """App instance: run_server defaults to 127.0.0.1:8000."""
        mock_app = MagicMock()
        mock_app.config = None
        fake_uvicorn = _FakeUvicorn()

        def _run() -> None:
            with patch.dict(
                "sys.modules",
                {"uvicorn": fake_uvicorn.make_module(), "granian": None, "granian.constants": None},
            ):
                from quadkit.web.server.runner import run_server

                run_server(mock_app)

        thread = threading.Thread(target=_run)
        thread.start()
        thread.join()

        assert len(fake_uvicorn.configs) == 1
        config = fake_uvicorn.configs[0]
        assert config.host == "127.0.0.1"
        assert config.port == 8000

    @pytest.mark.asyncio
    async def test_run_server_rejects_running_loop(self) -> None:
        """Sync run_server must not silently block a running event loop."""
        from quadkit.web.server.runner import run_server

        with pytest.raises(RuntimeError, match="run_server_async"):
            run_server("module:app")

    def test_config_workers_forwarded_to_sync_granian(self) -> None:
        """web.server.workers/reload reach the multiprocess supervisor.

        Regression: the runner read only host/port from config, so
        ``workers: 4`` in application.yaml was silently decorative.
        """
        mock_granian_cls = MagicMock()
        mock_granian_instance = MagicMock()
        mock_granian_cls.return_value = mock_granian_instance
        mock_granian_module = MagicMock()
        mock_granian_module.Granian = mock_granian_cls
        mock_constants_module = MagicMock()
        mock_constants_module.Interfaces = SimpleNamespace(ASGI="asgi")

        server_cfg = SimpleNamespace(
            backend="granian", host="127.0.0.1", port=9400, workers=3, reload=True
        )
        config = SimpleNamespace(
            get_section=lambda _name, _model: SimpleNamespace(server=server_cfg)
        )
        app = SimpleNamespace(config=config)

        with (
            patch.dict(
                "sys.modules",
                {
                    "granian": mock_granian_module,
                    "granian.constants": mock_constants_module,
                },
            ),
            patch(
                "quadkit.web.server.runner._to_import_string",
                return_value="module:create_app",
            ),
        ):
            from quadkit.web.server.runner import run_server

            run_server(app)

        call_kwargs = mock_granian_cls.call_args[1]
        assert call_kwargs["port"] == 9400
        assert call_kwargs["workers"] == 3
        assert call_kwargs["reload"] is True

    def test_import_string_underivable_returns_none(self) -> None:
        """No create_app in sight -> None, never an invented class path.

        The old fallback returned 'quadkit.app.base:Application', which a
        factory-mode server would happily construct and serve — a blank
        application instead of an honest fallback.
        """
        from quadkit.web.server.runner import _to_import_string

        assert _to_import_string(object()) is None


class TestRunServerAsync:
    """Test suite for run_server_async (async entry point)."""

    @pytest.mark.asyncio
    async def test_serves_uvicorn_in_loop(self) -> None:
        """Async run_server_async serves Uvicorn in the calling loop."""
        fake_uvicorn = _FakeUvicorn()

        with patch.dict(
            "sys.modules",
            {
                "uvicorn": fake_uvicorn.make_module(),
                "granian": None,
                "granian.constants": None,
            },
        ):
            from quadkit.web.server import run_server_async

            await run_server_async("module:app", host="127.0.0.1", port=9100)

        assert len(fake_uvicorn.configs) == 1
        config = fake_uvicorn.configs[0]
        assert config.app == "module:app"
        assert config.host == "127.0.0.1"
        assert config.port == 9100

    @pytest.mark.asyncio
    async def test_granian_async_serves_embedded_in_loop(self) -> None:
        """Async Granian serves the app object embedded, in the calling loop.

        SERVER-1 regression: the multiprocess ``Granian.serve()`` installs
        signal handlers, so dispatching it to an executor thread (the old
        behaviour, which this test used to assert) can never start. The
        async path must use ``granian.server.embed.Server`` awaited on
        the loop's own thread. The fake below records the thread its
        ``serve()`` ran on — a stand-in that cannot raise in an executor
        would pass vacuously, which is how the original bug shipped;
        ``tests/integration/test_runner_live.py`` drives the real server.
        """
        servers: list[Any] = []

        class FakeEmbedServer:
            def __init__(self, target: Any, **kwargs: Any) -> None:
                self.target = target
                self.kwargs = kwargs
                self.serve_thread: threading.Thread | None = None
                servers.append(self)

            async def serve(self) -> None:
                self.serve_thread = threading.current_thread()

            def stop(self) -> None:  # pragma: no cover - not exercised here
                pass

        embed_module = SimpleNamespace(Server=FakeEmbedServer)
        constants_module = SimpleNamespace(
            Interfaces=SimpleNamespace(ASGI="asgi")
        )
        app = object()

        with patch.dict(
            "sys.modules",
            {
                "granian": SimpleNamespace(),
                "granian.constants": constants_module,
                "granian.server.embed": embed_module,
            },
        ):
            from quadkit.web.server import run_server_async

            await run_server_async(
                app,
                host="127.0.0.1",
                port=9200,
                workers=2,
                ssl_certificate="cert.pem",
                pid_file="/var/run/x.pid",
            )

        assert len(servers) == 1
        server = servers[0]
        # The object passed in is the object served — no import-string
        # round-trip, no factory.
        assert server.target is app
        assert server.kwargs["address"] == "127.0.0.1"
        assert server.kwargs["port"] == 9200
        assert server.kwargs["interface"] == "asgi"
        assert server.kwargs["factory"] is False
        # Multiprocess kwargs are translated (ssl_certificate -> ssl_cert)
        # or dropped (pid_file, workers), never forwarded raw.
        assert server.kwargs["ssl_cert"] == "cert.pem"
        assert "workers" not in server.kwargs
        assert "pid_file" not in server.kwargs
        # And it all happened on the loop's thread, not an executor's.
        assert server.serve_thread is threading.main_thread()

    @pytest.mark.asyncio
    async def test_granian_async_string_factory_resolved(self) -> None:
        """A 'module:create_app' string resolves to a factory target."""
        servers: list[Any] = []

        class FakeEmbedServer:
            def __init__(self, target: Any, **kwargs: Any) -> None:
                self.target = target
                self.kwargs = kwargs
                servers.append(self)

            async def serve(self) -> None:
                pass

            def stop(self) -> None:  # pragma: no cover - not exercised here
                pass

        def create_app() -> object:
            return object()

        app_module = SimpleNamespace(create_app=create_app)
        with patch.dict(
            "sys.modules",
            {
                "granian": SimpleNamespace(),
                "granian.constants": SimpleNamespace(
                    Interfaces=SimpleNamespace(ASGI="asgi")
                ),
                "granian.server.embed": SimpleNamespace(Server=FakeEmbedServer),
                "some_app_module": app_module,
            },
        ):
            from quadkit.web.server import run_server_async

            await run_server_async("some_app_module:create_app", port=9201)

        assert len(servers) == 1
        assert servers[0].target is create_app
        assert servers[0].kwargs["factory"] is True

    @pytest.mark.asyncio
    async def test_unknown_backend_raises(self) -> None:
        """A configured backend outside the supported set is an error.

        The runner used to log 'hypercorn' (then unimplemented) or any
        other name and quietly serve Uvicorn. backend is an instruction:
        unknown names raise with the supported list.
        """
        server_cfg = SimpleNamespace(
            backend="daphne", host="127.0.0.1", port=9300, workers=1, reload=False
        )
        config = SimpleNamespace(
            get_section=lambda _name, _model: SimpleNamespace(server=server_cfg)
        )
        app = SimpleNamespace(config=config)

        with patch.dict("sys.modules", {"daphne": SimpleNamespace()}):
            from quadkit.web.server import run_server_async

            with pytest.raises(RuntimeError, match="Unsupported ASGI server backend"):
                await run_server_async(app)
