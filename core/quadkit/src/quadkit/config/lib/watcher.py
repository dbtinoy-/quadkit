"""Poll-based configuration change watcher for Quadkit Framework.

``ConfigWatcher`` monitors a configuration source for changes by computing a
SHA-256 hash of the serialised configuration on each poll interval. When the
hash changes, registered ``on_change`` callbacks are invoked with the old and
new config values.
"""

from __future__ import annotations

import asyncio
import hashlib
import json  # noqa: TID251
from typing import TYPE_CHECKING, Any
import weakref

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

logger = get_logger(__name__)


class ConfigWatcher:
    """Poll-based configuration change detector.

    Calls a user-supplied *loader* coroutine at each *interval* to retrieve
    the current configuration, then compares its SHA-256 hash to the last
    known hash. When a change is detected, all registered *on_change*
    callbacks are invoked concurrently with ``(old_config, new_config)``.

    Args:
        loader: An async callable that returns the current configuration dict.
        interval: Polling interval in seconds. Defaults to ``30.0``.

    Example::

        async def load_config() -> dict:
            return await settings.reload()

        watcher = ConfigWatcher(loader=load_config, interval=10.0)
        watcher.add_listener(on_change)
        await watcher.start()
        ...
        await watcher.stop()
    """

    def __init__(
        self,
        loader: Callable[[], Coroutine[Any, Any, dict[str, Any]]],
        *,
        interval: float = 30.0,
    ) -> None:
        self._loader = loader
        self._interval = interval
        self._listeners: weakref.WeakSet[
            Callable[
                [dict[str, Any], dict[str, Any]],
                Coroutine[Any, Any, None],
            ]
        ] = weakref.WeakSet()
        self._last_hash: str | None = None
        self._last_config: dict[str, Any] | None = None
        self._task: asyncio.Task[None] | None = None
        self._current_interval: float = interval
        self._max_interval: float = interval * 10

    # -- Lifecycle --

    async def start(self) -> None:
        """Start the background polling task.

        Re-entrant: calling ``start()`` on a running watcher is a no-op.
        """
        if self._task is not None and not self._task.done():
            logger.debug("config_watcher.start.already_running")
            return

        # Perform one immediate poll to establish a baseline
        await self._poll()

        # RUF006: store the task reference to prevent GC
        self._task = asyncio.create_task(self._run_loop(), name="config_watcher")
        logger.info("config_watcher.started", interval=self._interval)

    async def stop(self) -> None:
        """Cancel the background polling task and wait for it to finish.

        Safe to call even if the watcher is not running.
        """
        if self._task is None or self._task.done():
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
        logger.info("config_watcher.stopped")

    # -- Listener management --

    def add_listener(
        self,
        callback: Callable[
            [dict[str, Any], dict[str, Any]],
            Coroutine[Any, Any, None],
        ],
    ) -> None:
        """Register an async *callback* to be called when the config changes.

        Args:
            callback: Async callable with signature
                ``(old_config: dict, new_config: dict) -> None``.
        """
        self._listeners.add(callback)

    def remove_listener(
        self,
        callback: Callable[
            [dict[str, Any], dict[str, Any]],
            Coroutine[Any, Any, None],
        ],
    ) -> None:
        """Unregister a previously registered *callback*.

        Args:
            callback: The callback to remove. No-op if not found.
        """
        self._listeners.discard(callback)

    # -- Introspection --

    @property
    def is_running(self) -> bool:
        """Return True if the polling task is currently active.

        Returns:
            ``True`` if the watcher is running.
        """
        return self._task is not None and not self._task.done()

    @property
    def last_config(self) -> dict[str, Any] | None:
        """Return the most recently observed configuration, or ``None``.

        Returns:
            Last loaded config dict, or ``None`` before first poll.
        """
        return self._last_config

    # -- Internal --

    async def _run_loop(self) -> None:
        """Main polling loop; runs until cancelled."""
        while True:
            await asyncio.sleep(self._current_interval)
            await self._poll()

    async def _poll(self) -> None:
        """Load config and fire change callbacks if the hash has changed."""
        try:
            new_config = await self._loader()
            self._current_interval = self._interval  # Reset on success
        except Exception as exc:  # noqa: BLE001 — the watch loop must survive any loader error
            logger.warning("config_watcher.poll.error", error=str(exc))
            self._current_interval = min(self._current_interval * 2, self._max_interval)
            return

        new_hash = self._hash(new_config)
        if self._last_hash is None:
            # First poll — establish baseline
            self._last_hash = new_hash
            self._last_config = new_config
            logger.debug("config_watcher.poll.baseline", hash=new_hash[:8])
            return

        if new_hash == self._last_hash:
            logger.debug("config_watcher.poll.no_change")
            return

        old_config = self._last_config or {}
        logger.info("config_watcher.change_detected", new_hash=new_hash[:8])

        # Validate-before-swap: notify listeners BEFORE committing the new state.
        # If all listeners succeed, swap; if any raises, keep the old config.
        if self._listeners:
            results = await asyncio.gather(
                *[cb(old_config, new_config) for cb in list(self._listeners)],
                return_exceptions=True,
            )
            for result in results:
                if isinstance(result, BaseException):
                    logger.warning(
                        "config_watcher.listener_error",
                        error=str(result),
                    )
                    # Listener failed — do NOT swap state
                    return

        # All listeners accepted the new config; safe to commit
        self._last_hash = new_hash
        self._last_config = new_config

    @staticmethod
    def _hash(config: dict[str, Any]) -> str:
        """Compute a SHA-256 digest of the JSON-serialised *config*.

        Args:
            config: Configuration dict to hash.

        Returns:
            Hex-encoded SHA-256 digest string.
        """
        serialised = json.dumps(config, sort_keys=True, default=str)
        return hashlib.sha256(serialised.encode()).hexdigest()


__all__ = ["ConfigWatcher"]
