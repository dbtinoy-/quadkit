from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from quadkit.cli.registry.telemetry import (
    FileTelemetryBackend,
    HTTPTelemetryBackend,
    NoOpTelemetryBackend,
    TelemetryBackend,
    TelemetryEvent,
    TelemetryRegistry,
    disable_telemetry,
    enable_telemetry,
    get_telemetry_status,
    track_command,
)


class TestTelemetryEvent:
    def test_defaults(self) -> None:
        event = TelemetryEvent(event_type="test")
        assert event.event_type == "test"
        assert event.command is None
        assert event.extra == {}

    def test_custom(self) -> None:
        event = TelemetryEvent(
            event_type="cmd",
            command="run",
            duration_ms=100,
            success=True,
            extra={"key": "val"},
        )
        assert event.command == "run"
        assert event.duration_ms == 100


class TestTelemetryBackend:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            TelemetryBackend()


class TestNoOpTelemetryBackend:
    def test_send_returns_false(self) -> None:
        backend = NoOpTelemetryBackend()
        result = backend.send(TelemetryEvent(event_type="test"))
        assert result is False

    def test_flush(self) -> None:
        backend = NoOpTelemetryBackend()
        backend.flush()  # should not raise


class TestFileTelemetryBackend:
    def test_send_success(self) -> None:
        with patch("pathlib.Path.mkdir"):
            with patch("builtins.open", mock_open()) as m:
                backend = FileTelemetryBackend(file_path=Path("/tmp/test.log"))
                result = backend.send(TelemetryEvent(event_type="test", command="run"))
                assert result is True
                m().write.assert_called_once()

    def test_send_failure(self) -> None:
        backend = FileTelemetryBackend(file_path=Path("/nonexistent/test.log"))
        with patch("pathlib.Path.mkdir", side_effect=PermissionError):
            result = backend.send(TelemetryEvent(event_type="test"))
            assert result is False

    def test_flush(self) -> None:
        backend = FileTelemetryBackend()
        backend.flush()


class TestHTTPTelemetryBackend:
    def test_send_success(self) -> None:
        backend = HTTPTelemetryBackend("http://example.com")
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value.post = AsyncMock()

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = backend.send(TelemetryEvent(event_type="test"))
            assert result is True

    def test_flush(self) -> None:
        backend = HTTPTelemetryBackend()
        backend._pending = [TelemetryEvent(event_type="test")]
        backend.flush()
        assert backend._pending == []


class TestTelemetryRegistry:
    def test_disabled_by_default(self) -> None:
        TelemetryRegistry._enabled = False
        TelemetryRegistry._initialized = True
        assert TelemetryRegistry.is_enabled() is False

    def test_enable(self) -> None:
        TelemetryRegistry._initialized = True
        TelemetryRegistry.enable()
        assert TelemetryRegistry.is_enabled() is True

    def test_disable(self) -> None:
        TelemetryRegistry._initialized = True
        TelemetryRegistry.enable()
        TelemetryRegistry.disable()
        assert TelemetryRegistry.is_enabled() is False

    def test_track_when_disabled(self) -> None:
        TelemetryRegistry._initialized = True
        TelemetryRegistry._enabled = False
        backend = MagicMock(spec=TelemetryBackend)
        TelemetryRegistry._backend = backend
        TelemetryRegistry.track("test_cmd")
        backend.send.assert_not_called()

    def test_track_when_enabled(self) -> None:
        TelemetryRegistry._initialized = True
        TelemetryRegistry._enabled = True
        backend = MagicMock(spec=TelemetryBackend)
        TelemetryRegistry._backend = backend
        TelemetryRegistry.track("test_cmd", duration_ms=50, success=True)
        backend.send.assert_called_once()

    def test_track_error_when_disabled(self) -> None:
        TelemetryRegistry._initialized = True
        TelemetryRegistry._enabled = False
        backend = MagicMock(spec=TelemetryBackend)
        TelemetryRegistry._backend = backend
        TelemetryRegistry.track_error("test_cmd", "ValueError")
        backend.send.assert_not_called()

    def test_track_error_when_enabled(self) -> None:
        TelemetryRegistry._initialized = True
        TelemetryRegistry._enabled = True
        backend = MagicMock(spec=TelemetryBackend)
        TelemetryRegistry._backend = backend
        TelemetryRegistry.track_error("test_cmd", "ValueError")
        backend.send.assert_called_once()

    def test_flush(self) -> None:
        backend = MagicMock(spec=TelemetryBackend)
        TelemetryRegistry._backend = backend
        TelemetryRegistry.flush()
        backend.flush.assert_called_once()

    def test_set_backend(self) -> None:
        backend = MagicMock(spec=TelemetryBackend)
        TelemetryRegistry.set_backend(backend)
        assert TelemetryRegistry._backend is backend


class TestTrackCommandDecorator:
    def test_decorator_tracks_success(self) -> None:
        TelemetryRegistry._initialized = True
        TelemetryRegistry._enabled = True
        backend = MagicMock(spec=TelemetryBackend)
        TelemetryRegistry._backend = backend

        @track_command("test_cmd")
        def my_func():
            return 42

        result = my_func()
        assert result == 42
        backend.send.assert_called_once()

    def test_decorator_tracks_error(self) -> None:
        TelemetryRegistry._initialized = True
        TelemetryRegistry._enabled = True
        backend = MagicMock(spec=TelemetryBackend)
        TelemetryRegistry._backend = backend

        @track_command("test_cmd")
        def failing_func():
            raise ValueError("oops")

        with pytest.raises(ValueError):
            failing_func()
        backend.send.assert_called_once()


class TestTelemetryHelpers:
    def test_enable_telemetry(self) -> None:
        TelemetryRegistry._initialized = True
        enable_telemetry()
        assert TelemetryRegistry._enabled is True
        assert TelemetryRegistry._backend.name == "file"

    def test_disable_telemetry(self) -> None:
        TelemetryRegistry._initialized = True
        TelemetryRegistry._enabled = True
        disable_telemetry()
        assert TelemetryRegistry._enabled is False

    def test_get_telemetry_status(self) -> None:
        TelemetryRegistry._initialized = True
        TelemetryRegistry._enabled = True
        status = get_telemetry_status()
        assert status["enabled"] is True
        assert "backend" in status
