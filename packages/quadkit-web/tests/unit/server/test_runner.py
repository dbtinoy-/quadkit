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
        assert config.kwargs == {"workers": 2}

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
    async def test_granian_runs_in_executor(self) -> None:
        """Async run_server_async runs Granian off the calling loop."""
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
            from quadkit.web.server import run_server_async

            await run_server_async("module:app", host="127.0.0.1", port=9200, workers=2)

        mock_granian_cls.assert_called_once()
        call_args = mock_granian_cls.call_args
        assert call_args[0][0] == "module:app"
        assert call_args[1]["address"] == "127.0.0.1"
        assert call_args[1]["port"] == 9200
        assert call_args[1]["workers"] == 2
        mock_granian_instance.serve.assert_called_once()
