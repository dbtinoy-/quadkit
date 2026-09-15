"""Telemetry registry for anonymous usage analytics.

This module provides opt-in telemetry for the CLI.
"""

from __future__ import annotations

import abc
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import platform
from typing import Any, ParamSpec, TypeVar

from quadkit import serialization as json
from quadkit.logging import get_logger

logger = get_logger(__name__)

TELEMETRY_CONFIG_PATH = Path.home() / ".quadkit" / "config.toml"
DEFAULT_ENDPOINT = "https://telemetry.quadkit.io/v1/events"


@dataclass
class TelemetryEvent:
    """A telemetry event."""

    event_type: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    command: str | None = None
    duration_ms: int | None = None
    success: bool | None = None
    framework_version: str | None = None
    python_version: str | None = None
    os: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class TelemetryBackend(abc.ABC):
    """Abstract base class for telemetry backends."""

    name: str

    @abc.abstractmethod
    def send(self, event: TelemetryEvent) -> bool:
        """Send a telemetry event. Returns True if successful."""

    @abc.abstractmethod
    def flush(self) -> None:
        """Flush any pending events."""


class NoOpTelemetryBackend(TelemetryBackend):
    """No-op backend that discards all events."""

    name = "noop"

    def send(self, event: TelemetryEvent) -> bool:
        return False

    def flush(self) -> None:
        pass


class FileTelemetryBackend(TelemetryBackend):
    """File-based backend for local testing."""

    name = "file"

    def __init__(self, file_path: Path | None = None):
        self.file_path = file_path or Path.home() / ".quadkit" / "telemetry.log"

    def send(self, event: TelemetryEvent) -> bool:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "a") as f:
                f.write(
                    json.dumps_str(
                        {
                            "event_type": event.event_type,
                            "timestamp": event.timestamp,
                            "command": event.command,
                            "duration_ms": event.duration_ms,
                            "success": event.success,
                            "framework_version": event.framework_version,
                            "python_version": event.python_version,
                            "os": event.os,
                            "extra": event.extra,
                        },
                    )
                    + "\n",
                )
            return True
        except Exception:  # noqa: BLE001 — telemetry flush degrades to False
            return False

    def flush(self) -> None:
        """No-op — events are written to the file immediately on send."""


class HTTPTelemetryBackend(TelemetryBackend):
    """HTTP backend for sending telemetry to a remote endpoint."""

    def __init__(self, endpoint: str = DEFAULT_ENDPOINT) -> None:
        self.endpoint = endpoint
        self._pending: list[TelemetryEvent] = []

    def send(self, event: TelemetryEvent) -> bool:
        try:
            import asyncio

            import httpx

            async def _send() -> None:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    await client.post(
                        self.endpoint,
                        json={
                            "event_type": event.event_type,
                            "timestamp": event.timestamp,
                            "command": event.command,
                            "duration_ms": event.duration_ms,
                            "success": event.success,
                            "framework_version": event.framework_version,
                            "python_version": event.python_version,
                            "os": event.os,
                            "extra": event.extra,
                        },
                    )

            asyncio.run(_send())
            return True
        except Exception:  # noqa: BLE001 — telemetry event capture never raises
            self._pending.append(event)
            return False

    def flush(self) -> None:
        self._pending.clear()


class TelemetryRegistry:
    """Registry for telemetry management."""

    _enabled: bool = False
    _backend: TelemetryBackend = NoOpTelemetryBackend()
    _initialized: bool = False
    _user_id: str | None = None

    @classmethod
    def is_enabled(cls) -> bool:
        """Check if telemetry is enabled."""
        cls._ensure_config_loaded()
        return cls._enabled

    @classmethod
    def enable(cls) -> None:
        """Enable telemetry."""
        cls._enabled = True

    @classmethod
    def disable(cls) -> None:
        """Disable telemetry."""
        cls._enabled = False
        cls._backend = NoOpTelemetryBackend()

    @classmethod
    def set_backend(cls, backend: TelemetryBackend) -> None:
        """Set the telemetry backend."""
        cls._backend = backend

    @classmethod
    def track(
        cls,
        command: str,
        duration_ms: int | None = None,
        success: bool | None = None,
        **extra: Any,
    ) -> None:
        """Track a command execution."""
        if not cls._enabled:
            return

        event = TelemetryEvent(
            event_type="command_executed",
            command=command,
            duration_ms=duration_ms,
            success=success,
            framework_version=cls._get_framework_version(),
            python_version=platform.python_version(),
            os=platform.system(),
            extra=extra,
        )
        cls._backend.send(event)

    @classmethod
    def track_error(cls, command: str, error_type: str, **extra: Any) -> None:
        """Track a command error."""
        if not cls._enabled:
            return

        event = TelemetryEvent(
            event_type="command_error",
            command=command,
            success=False,
            framework_version=cls._get_framework_version(),
            python_version=platform.python_version(),
            os=platform.system(),
            extra={"error_type": error_type, **extra},
        )
        cls._backend.send(event)

    @classmethod
    def flush(cls) -> None:
        """Flush pending telemetry events."""
        cls._backend.flush()

    @classmethod
    def _ensure_config_loaded(cls) -> None:
        """Load telemetry configuration."""
        if cls._initialized:
            return

        cls._initialized = True

        if not TELEMETRY_CONFIG_PATH.exists():
            return

        try:
            import tomllib

            with open(TELEMETRY_CONFIG_PATH, "rb") as f:
                config = tomllib.load(f)

            telemetry_config = config.get("telemetry", {})
            cls._enabled = telemetry_config.get("enabled", False)

            if cls._enabled:
                backend_type = telemetry_config.get("backend", "file")
                if backend_type == "http":
                    endpoint = telemetry_config.get("endpoint", DEFAULT_ENDPOINT)
                    cls._backend = HTTPTelemetryBackend(endpoint)
                else:
                    file_path = telemetry_config.get("file_path")
                    cls._backend = FileTelemetryBackend(
                        Path(file_path) if file_path else None,
                    )
        except Exception as exc:  # noqa: BLE001 — telemetry write failures are logged, never raised
            logger.debug("telemetry_write_failed", error=str(exc))

    @classmethod
    def _get_framework_version(cls) -> str | None:
        """Get the framework version."""
        try:
            import importlib.metadata

            try:
                return importlib.metadata.version("quadkit")
            except importlib.metadata.PackageNotFoundError:
                return "0.0.0-dev"
        except Exception:  # noqa: BLE001 — telemetry read degrades to None
            return None


P = ParamSpec("P")
R = TypeVar("R")


def track_command(command: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to track command execution."""

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = datetime.now(UTC)
            success = True
            error_type = None

            try:
                return func(*args, **kwargs)
            except Exception as e:
                success = False
                error_type = type(e).__name__
                raise
            finally:
                duration = int((datetime.now(UTC) - start).total_seconds() * 1000)

                if success:
                    TelemetryRegistry.track(command, duration_ms=duration, success=True)
                else:
                    TelemetryRegistry.track_error(command, error_type or "unknown")

        return wrapper

    return decorator


def enable_telemetry(backend: TelemetryBackend | None = None) -> None:
    """Enable telemetry with optional custom backend."""
    TelemetryRegistry.enable()
    if backend:
        TelemetryRegistry.set_backend(backend)
    else:
        TelemetryRegistry.set_backend(FileTelemetryBackend())


def disable_telemetry() -> None:
    """Disable telemetry."""
    TelemetryRegistry.disable()


def get_telemetry_status() -> dict[str, Any]:
    """Get telemetry status."""
    return {
        "enabled": TelemetryRegistry.is_enabled(),
        "backend": TelemetryRegistry._backend.name,
    }


__all__ = [
    "FileTelemetryBackend",
    "HTTPTelemetryBackend",
    "NoOpTelemetryBackend",
    "TelemetryBackend",
    "TelemetryEvent",
    "TelemetryRegistry",
    "disable_telemetry",
    "enable_telemetry",
    "get_telemetry_status",
    "track_command",
]
