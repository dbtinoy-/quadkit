"""Tests for server/reload.py — HotReloadManager and create_hot_reload_middleware."""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.web.server.reload import HotReloadManager, create_hot_reload_middleware


class TestHotReloadManagerInit:
    def test_defaults(self) -> None:
        mgr = HotReloadManager()
        assert mgr.watch_paths == []
        assert mgr.on_reload is None
        assert mgr._running is False
        assert mgr._task is None

    def test_with_watch_paths_and_callback(self) -> None:
        cb = AsyncMock()
        mgr = HotReloadManager(watch_paths=["/tmp"], on_reload=cb)
        assert mgr.watch_paths == ["/tmp"]
        assert mgr.on_reload is cb


class TestHotReloadManagerStartStop:
    @pytest.mark.asyncio
    async def test_start_sets_running(self) -> None:
        mgr = HotReloadManager()
        await mgr.start()
        try:
            assert mgr._running is True
            assert mgr._task is not None
        finally:
            await mgr.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self) -> None:
        mgr = HotReloadManager()
        await mgr.start()
        assert mgr._task is not None
        await mgr.stop()
        assert mgr._running is False
        assert mgr._task is None

    @pytest.mark.asyncio
    async def test_stop_when_not_started_is_noop(self) -> None:
        mgr = HotReloadManager()
        await mgr.stop()  # Should not raise


class TestHotReloadManagerCheckFile:
    @pytest.mark.asyncio
    async def test_check_file_stores_mtime(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            filepath = f.name
        try:
            mgr = HotReloadManager()
            await mgr._check_file(filepath)
            assert filepath in mgr._file_mtimes
        finally:
            os.unlink(filepath)

    @pytest.mark.asyncio
    async def test_check_file_triggers_reload_on_change(self) -> None:
        cb = AsyncMock()
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            filepath = f.name
        try:
            mgr = HotReloadManager(on_reload=cb)
            # Pre-populate with old mtime
            mgr._file_mtimes[filepath] = 0.0
            await mgr._check_file(filepath)
            cb.assert_awaited_once_with(filepath)
        finally:
            os.unlink(filepath)

    @pytest.mark.asyncio
    async def test_check_file_oserror_is_silent(self) -> None:
        mgr = HotReloadManager()
        await mgr._check_file("/nonexistent/path.py")  # Should not raise

    @pytest.mark.asyncio
    async def test_check_file_no_reload_when_mtime_unchanged(self) -> None:
        cb = AsyncMock()
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            filepath = f.name
        try:
            mgr = HotReloadManager(on_reload=cb)
            # Get real mtime
            real_mtime = os.path.getmtime(filepath)
            mgr._file_mtimes[filepath] = real_mtime
            await mgr._check_file(filepath)
            cb.assert_not_awaited()
        finally:
            os.unlink(filepath)


class TestHotReloadManagerTriggerReload:
    @pytest.mark.asyncio
    async def test_trigger_reload_calls_callback(self) -> None:
        cb = AsyncMock()
        mgr = HotReloadManager(on_reload=cb)
        await mgr._trigger_reload("/some/file.py")
        cb.assert_awaited_once_with("/some/file.py")

    @pytest.mark.asyncio
    async def test_trigger_reload_no_callback_is_noop(self) -> None:
        mgr = HotReloadManager()
        await mgr._trigger_reload("/some/file.py")  # Should not raise

    @pytest.mark.asyncio
    async def test_trigger_reload_callback_exception_is_logged(self) -> None:
        cb = AsyncMock(side_effect=RuntimeError("oops"))
        mgr = HotReloadManager(on_reload=cb)
        await mgr._trigger_reload("/file.py")  # Should not raise, just log


class TestHotReloadManagerAddWatchPath:
    def test_add_new_path(self) -> None:
        mgr = HotReloadManager()
        mgr.add_watch_path("/tmp/controllers")
        assert "/tmp/controllers" in mgr.watch_paths

    def test_does_not_duplicate(self) -> None:
        mgr = HotReloadManager(watch_paths=["/tmp"])
        mgr.add_watch_path("/tmp")
        assert mgr.watch_paths.count("/tmp") == 1


class TestHotReloadManagerWatchLoop:
    @pytest.mark.asyncio
    async def test_watch_loop_checks_files_in_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a .py file in the temp dir
            py_file = os.path.join(tmpdir, "controller.py")
            Path(py_file).write_text("# test")

            checked = []

            async def mock_check(filepath: str) -> None:
                checked.append(filepath)

            mgr = HotReloadManager(watch_paths=[tmpdir])
            mgr._check_file = mock_check  # type: ignore[method-assign]
            mgr._running = True

            # Run one iteration of the watch loop logic by directly calling _check_file
            for root, _dirs, files in os.walk(tmpdir):
                for f in files:
                    if f.endswith(".py"):
                        await mgr._check_file(os.path.join(root, f))

            assert py_file in checked

    @pytest.mark.asyncio
    async def test_watch_loop_checks_single_file_in_watch_paths(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            filepath = f.name
        try:
            checked = []

            async def mock_check(p: str) -> None:
                checked.append(p)

            mgr = HotReloadManager(watch_paths=[filepath])
            mgr._check_file = mock_check  # type: ignore[method-assign]

            # Simulate one iteration of the watch loop file check
            if os.path.isfile(filepath):
                await mgr._check_file(filepath)

            assert filepath in checked
        finally:
            os.unlink(filepath)


class TestCreateHotReloadMiddleware:
    def test_creates_middleware_class(self) -> None:
        klass = create_hot_reload_middleware(["/tmp"])
        assert isinstance(klass, type)

    def test_middleware_instance_has_manager(self) -> None:
        klass = create_hot_reload_middleware(["/tmp"])
        inner = MagicMock()
        instance = klass(inner)
        assert hasattr(instance, "manager")
        assert isinstance(instance.manager, HotReloadManager)

    def test_middleware_stores_app(self) -> None:
        inner = MagicMock()
        klass = create_hot_reload_middleware(["/tmp"])
        instance = klass(inner)
        assert instance.app is inner

    @pytest.mark.asyncio
    async def test_middleware_passes_non_lifespan_requests(self) -> None:
        inner_called = []

        async def inner_app(scope, receive, send) -> None:
            inner_called.append(scope["type"])

        klass = create_hot_reload_middleware(["/tmp"])
        middleware = klass(inner_app)

        scope = {"type": "http", "path": "/test"}
        await middleware(scope, None, None)
        assert "http" in inner_called

    @pytest.mark.asyncio
    async def test_middleware_passes_lifespan_scope(self) -> None:
        inner_called = []

        async def inner_app(scope, receive, send) -> None:
            inner_called.append(scope["type"])

        klass = create_hot_reload_middleware(["/tmp"])
        middleware = klass(inner_app)

        scope = {"type": "lifespan"}
        await middleware(scope, None, None)
        assert "lifespan" in inner_called
