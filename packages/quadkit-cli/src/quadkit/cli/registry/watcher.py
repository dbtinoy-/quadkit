"""Watcher registry for file watching and auto-reload.

This module provides a registry pattern for file watchers.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass
class WatchEvent:
    """Represents a file change event."""

    event_type: str
    path: Path
    timestamp: float = field(default_factory=time.time)


@dataclass
class WatchConfig:
    """Configuration for file watching."""

    paths: list[str] = field(default_factory=lambda: ["."])
    patterns: list[str] = field(default_factory=lambda: ["*.py", "*.yaml", "*.yml"])
    ignore_patterns: list[str] = field(
        default_factory=lambda: ["__pycache__", "*.pyc", ".git", "node_modules"],
    )
    debounce_ms: int = 500


class Watcher(abc.ABC):
    """Abstract base class for file watchers."""

    name: str

    @abc.abstractmethod
    def start(self, callback: Callable[[list[WatchEvent]], None]) -> None:
        """Start watching for file changes."""

    @abc.abstractmethod
    def stop(self) -> None:
        """Stop watching for file changes."""

    @abc.abstractmethod
    def is_running(self) -> bool:
        """Check if watcher is running."""


class WatchfilesWatcher(Watcher):
    """Watcher using the watchfiles library."""

    name = "watchfiles"

    def __init__(self, config: WatchConfig | None = None):
        self.config = config or WatchConfig()
        self._running = False
        self._process = None

    def start(self, callback: Callable[[list[WatchEvent]], None]) -> None:
        try:
            from watchfiles import watch
        except ImportError:
            raise ImportError("watchfiles not installed") from None

        self._running = True

        for changes in watch(*self.config.paths, **self._get_watch_kwargs()):
            if not self._running:
                break

            events = []
            for change_type, path in changes:
                events.append(
                    WatchEvent(
                        event_type=change_type.name,
                        path=Path(path),
                    ),
                )

            if events:
                callback(events)

    def stop(self) -> None:
        self._running = False

    def is_running(self) -> bool:
        return self._running

    def _get_watch_kwargs(self) -> dict[str, Any]:
        kwargs = {}
        if self.config.ignore_patterns:
            kwargs["ignore_add"] = self.config.ignore_patterns
        return kwargs


class PollingWatcher(Watcher):
    """Simple polling-based watcher (no external dependencies)."""

    name = "polling"

    def __init__(self, config: WatchConfig | None = None):
        self.config = config or WatchConfig()
        self._running = False
        self._last_modified: dict[Path, float] = {}
        self._callback: Callable[[list[WatchEvent]], None] | None = None
        self._stop_event: Any = None

    def start(self, callback: Callable[[list[WatchEvent]], None]) -> None:
        self._running = True
        self._callback = callback

        import threading

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._stop_event:
            self._stop_event.set()

    def is_running(self) -> bool:
        return self._running

    def _poll_loop(self) -> None:
        while self._running and not self._stop_event.is_set():
            events = self._check_for_changes()
            if events and self._callback:
                self._callback(events)
            time.sleep(self.config.debounce_ms / 1000)

    def _check_for_changes(self) -> list[WatchEvent]:
        events = []

        for path_pattern in self.config.paths:
            path = Path(path_pattern)
            if path.is_file():
                modified = path.stat().st_mtime
                if path not in self._last_modified:
                    self._last_modified[path] = modified
                elif self._last_modified[path] != modified:
                    events.append(WatchEvent(event_type="modified", path=path))
                    self._last_modified[path] = modified
            elif path.is_dir():
                for pattern in self.config.patterns:
                    for file_path in path.rglob(pattern):
                        if self._should_ignore(file_path):
                            continue
                        try:
                            modified = file_path.stat().st_mtime
                            if file_path not in self._last_modified:
                                self._last_modified[file_path] = modified
                                events.append(
                                    WatchEvent(event_type="created", path=file_path),
                                )
                            elif self._last_modified[file_path] != modified:
                                events.append(
                                    WatchEvent(event_type="modified", path=file_path),
                                )
                                self._last_modified[file_path] = modified
                        except OSError:
                            pass

        return events

    def _should_ignore(self, path: Path) -> bool:
        path_str = str(path)
        return any(pattern in path_str for pattern in self.config.ignore_patterns)


class WatcherRegistry:
    """Registry for file watchers.

    Provides a pluggable way to add new watchers.
    """

    def __init__(self) -> None:
        self._watchers: dict[str, type[Watcher]] = {}

    def register(self, watcher: type[Watcher]) -> None:
        """Register a watcher class."""
        self._watchers[watcher.name] = watcher

    def get(self, name: str) -> type[Watcher] | None:
        """Get a watcher class by name."""
        return self._watchers.get(name)

    def get_all(self) -> dict[str, type[Watcher]]:
        """Get all registered watchers."""
        return self._watchers.copy()

    def get_choices(self) -> list[str]:
        """Get list of available watcher names."""
        return list(self._watchers.keys())

    @classmethod
    def _default_entries(cls) -> tuple[type[Watcher], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            WatchfilesWatcher,
            PollingWatcher,
        )

    @classmethod
    def with_defaults(cls) -> WatcherRegistry:
        """Return an instance populated with the built-in watchers."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


def create_watcher(name: str = "auto", config: WatchConfig | None = None) -> Watcher:
    """Factory function to create a watcher."""
    registry = WatcherRegistry.with_defaults()
    if name == "auto":
        if WatchfilesWatcher.name in registry.get_choices():
            name = "watchfiles"
        else:
            name = "polling"

    watcher_class = registry.get(name)
    if not watcher_class:
        watcher_class = PollingWatcher

    return watcher_class(config)  # type: ignore[call-arg]


__all__ = [
    "PollingWatcher",
    "WatchConfig",
    "WatchEvent",
    "Watcher",
    "WatcherRegistry",
    "WatchfilesWatcher",
    "create_watcher",
]
