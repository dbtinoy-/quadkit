from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quadkit.cli.registry.watcher import (
    PollingWatcher,
    WatchConfig,
    WatchEvent,
    Watcher,
    WatcherRegistry,
    WatchfilesWatcher,
    create_watcher,
)


class TestWatchEvent:
    def test_creation(self) -> None:
        event = WatchEvent(event_type="modified", path=Path("/test/file.py"))
        assert event.event_type == "modified"
        assert str(event.path) == "/test/file.py"
        assert event.timestamp > 0


class TestWatchConfig:
    def test_defaults(self) -> None:
        config = WatchConfig()
        assert config.paths == ["."]
        assert "*.py" in config.patterns
        assert "__pycache__" in config.ignore_patterns
        assert config.debounce_ms == 500

    def test_custom(self) -> None:
        config = WatchConfig(paths=["/src"], patterns=["*.go"])
        assert config.paths == ["/src"]
        assert config.patterns == ["*.go"]


class TestWatcher:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            Watcher()


class TestWatchfilesWatcher:
    def test_init(self) -> None:
        w = WatchfilesWatcher()
        assert w._running is False

    def test_stop(self) -> None:
        w = WatchfilesWatcher()
        w.start = MagicMock()
        w._running = True
        w.stop()
        assert w._running is False

    def test_is_running(self) -> None:
        w = WatchfilesWatcher()
        assert w.is_running() is False
        w._running = True
        assert w.is_running() is True

    def test_start_no_watchfiles(self) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "watchfiles":
                raise ImportError
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            w = WatchfilesWatcher()
            with pytest.raises(ImportError):
                w.start(lambda x: None)


class TestPollingWatcher:
    def test_init(self) -> None:
        w = PollingWatcher()
        assert w._running is False

    def test_start_stop(self) -> None:
        w = PollingWatcher()
        w.start(lambda events: None)
        assert w._running is True
        w.stop()
        assert w._running is False

    def test_is_running(self) -> None:
        w = PollingWatcher()
        assert w.is_running() is False

    def test_check_for_changes_file(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("content")
        w = PollingWatcher(WatchConfig(paths=[str(test_file)]))
        events = w._check_for_changes()
        assert len(events) == 0  # first call populates the snapshot

    def test_check_for_changes_dir(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        test_file = tmp_path / "sub" / "test.py"
        test_file.write_text("content")
        w = PollingWatcher(WatchConfig(paths=[str(tmp_path)], patterns=["*.py"]))
        events = w._check_for_changes()
        assert len(events) >= 1

    def test_should_ignore(self, tmp_path: Path) -> None:
        w = PollingWatcher(WatchConfig(ignore_patterns=["__pycache__"]))
        ignored_path = tmp_path / "__pycache__" / "test.py"
        assert w._should_ignore(ignored_path) is True

    def test_should_not_ignore(self, tmp_path: Path) -> None:
        w = PollingWatcher(WatchConfig(ignore_patterns=["__pycache__"]))
        normal_path = tmp_path / "test.py"
        assert w._should_ignore(normal_path) is False

    def test_stop_clears_stop_event(self) -> None:
        w = PollingWatcher()
        w.start(lambda events: None)
        w.stop()
        assert w._running is False


class TestWatcherRegistry:
    def test_get_default_watchers(self) -> None:
        reg = WatcherRegistry.with_defaults()
        assert reg.get("polling") is not None

    def test_get_nonexistent(self) -> None:
        reg = WatcherRegistry.with_defaults()
        assert reg.get("nonexistent") is None

    def test_get_all(self) -> None:
        reg = WatcherRegistry.with_defaults()
        all_watchers = reg.get_all()
        assert "polling" in all_watchers

    def test_get_choices(self) -> None:
        reg = WatcherRegistry.with_defaults()
        choices = reg.get_choices()
        assert "polling" in choices

    def test_custom_registration(self) -> None:
        reg = WatcherRegistry.with_defaults()

        class FakeWatcher(Watcher):
            name = "fake"

            def start(self, callback):
                pass

            def stop(self):
                pass

            def is_running(self):
                return False

        reg.register(FakeWatcher)
        assert reg.get("fake") is FakeWatcher


class TestCreateWatcher:
    def test_create_polling(self) -> None:
        with patch.object(WatchfilesWatcher, "name", "watchfiles"):
            watcher = create_watcher(name="polling")
            assert isinstance(watcher, PollingWatcher)

    def test_create_nonexistent_fallback(self) -> None:
        watcher = create_watcher(name="nonexistent")
        assert isinstance(watcher, PollingWatcher)
