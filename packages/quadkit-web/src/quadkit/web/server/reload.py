"""Hot reload hook for development.

Detects file changes and reloads routes/controllers.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)


class HotReloadManager:
    """Manages hot reload for routes and controllers during development."""

    def __init__(
        self,
        watch_paths: list[str] | None = None,
        on_reload: Callable | None = None,
    ):
        self.watch_paths = watch_paths or []
        self.on_reload = on_reload
        self._running = False
        self._file_mtimes: dict[str, float] = {}
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start watching for file changes."""
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())

    async def stop(self) -> None:
        """Stop watching for file changes."""
        self._running = False
        if self._task is not None and not self._task.done():
            self._task.cancel()
            self._task = None

    async def _watch_loop(self) -> None:
        """Watch loop that checks for file changes."""
        while self._running:
            await asyncio.sleep(1.0)  # Check every second

            for path in self.watch_paths:
                if os.path.isfile(path):
                    await self._check_file(path)
                elif os.path.isdir(path):
                    for root, _dirs, files in os.walk(path):
                        for f in files:
                            if f.endswith(".py"):
                                await self._check_file(os.path.join(root, f))

    async def _check_file(self, filepath: str) -> None:
        """Check if a file has been modified."""
        try:
            mtime = os.path.getmtime(filepath)

            if filepath in self._file_mtimes:
                if mtime > self._file_mtimes[filepath]:
                    # File was modified
                    await self._trigger_reload(filepath)

            self._file_mtimes[filepath] = mtime
        except OSError:
            pass

    async def _trigger_reload(self, filepath: str) -> None:
        """Trigger a reload when a file changes."""
        if self.on_reload:
            try:
                await self.on_reload(filepath)
            except (RuntimeError, OSError) as exc:
                logger.debug("reload_handler_failed", error=str(exc))

    def add_watch_path(self, path: str) -> None:
        """Add a path to watch."""
        if path not in self.watch_paths:
            self.watch_paths.append(path)


def create_hot_reload_middleware(
    watch_paths: list[str],
    on_reload: Callable | None = None,
) -> type:
    """Create a hot reload middleware.

    Usage:
        app.add_middleware(
            HotReloadMiddleware,
            watch_paths=["/path/to/controllers"],
        )
    """

    class HotReloadMiddleware:
        def __init__(self, app: Any) -> None:
            self.app = app
            self.manager = HotReloadManager(
                watch_paths=watch_paths,
                on_reload=on_reload,
            )

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            if scope["type"] == "lifespan":
                # Add startup/shutdown handlers
                async def on_startup() -> None:
                    await self.manager.start()

                async def on_shutdown() -> None:
                    await self.manager.stop()

                # This is a simplified implementation
                # In practice, you'd integrate with the lifespan context
                await self.app(scope, receive, send)
            else:
                await self.app(scope, receive, send)

    return HotReloadMiddleware
