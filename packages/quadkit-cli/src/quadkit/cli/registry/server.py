"""Server backend registry for dev and start commands.

This module provides a registry pattern for supporting multiple ASGI server backends.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import ClassVar


@dataclass
class ServerConfig:
    """Configuration for running a server."""

    entry_point: str
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1
    reload: bool = False
    env: dict[str, str] | None = None
    factory: bool = False

    def __post_init__(self) -> None:
        if self.env is None:
            self.env = {}


class ServerBackend(abc.ABC):
    """Abstract base class for server backends."""

    name: ClassVar[str]
    package: ClassVar[str | None] = None

    @abc.abstractmethod
    def get_binary(self) -> str | None:
        """Get the path to the server binary."""

    @abc.abstractmethod
    def build_start_command(self, config: ServerConfig) -> list[str]:
        """Build the command to start the server."""

    @abc.abstractmethod
    def build_dev_command(self, config: ServerConfig) -> list[str]:
        """Build the command to start the server in development mode."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check if this server backend is available."""


class UvicornBackend(ServerBackend):
    """Uvicorn ASGI server."""

    name = "uvicorn"
    package = "uvicorn"

    def get_binary(self) -> str | None:
        return shutil.which("uvicorn")

    def build_start_command(self, config: ServerConfig) -> list[str]:
        cmd = [
            "uvicorn",
            config.entry_point,
            "--host",
            config.host,
            "--port",
            str(config.port),
        ]
        if config.workers > 1:
            cmd.extend(["--workers", str(config.workers)])
        if config.factory:
            cmd.append("--factory")
        return cmd

    def build_dev_command(self, config: ServerConfig) -> list[str]:
        cmd = [
            "uvicorn",
            config.entry_point,
            "--host",
            config.host,
            "--port",
            str(config.port),
            "--reload",
        ]
        if config.factory:
            cmd.append("--factory")
        return cmd

    def is_available(self) -> bool:
        return self.get_binary() is not None


class HypercornBackend(ServerBackend):
    """Hypercorn ASGI server."""

    name = "hypercorn"
    package = "hypercorn"

    def get_binary(self) -> str | None:
        return shutil.which("hypercorn")

    def build_start_command(self, config: ServerConfig) -> list[str]:
        cmd = [
            "hypercorn",
            config.entry_point,
            "--bind",
            f"{config.host}:{config.port}",
        ]
        if config.workers > 1:
            cmd.extend(["--workers", str(config.workers)])
        return cmd

    def build_dev_command(self, config: ServerConfig) -> list[str]:
        return [
            "hypercorn",
            config.entry_point,
            "--bind",
            f"{config.host}:{config.port}",
            "--reload",
        ]

    def is_available(self) -> bool:
        return self.get_binary() is not None


class GranianBackend(ServerBackend):
    """Granian ASGI server (Rust-based, high performance)."""

    name = "granian"
    package = "granian"

    def get_binary(self) -> str | None:
        return shutil.which("granian")

    def build_start_command(self, config: ServerConfig) -> list[str]:
        cmd = [
            "granian",
            "--interface",
            "asgi",
            "--host",
            config.host,
            "--port",
            str(config.port),
            config.entry_point,
        ]
        if config.workers > 1:
            cmd.extend(["--workers", str(config.workers)])
        return cmd

    def build_dev_command(self, config: ServerConfig) -> list[str]:
        return [
            "granian",
            "--interface",
            "asgi",
            "--host",
            config.host,
            "--port",
            str(config.port),
            "--reload",
            config.entry_point,
        ]

    def is_available(self) -> bool:
        return self.get_binary() is not None


class GunicornBackend(ServerBackend):
    """Gunicorn WSGI server (with gunicorn workers for ASGI)."""

    name = "gunicorn"
    package = "gunicorn"

    def get_binary(self) -> str | None:
        return shutil.which("gunicorn")

    def build_start_command(self, config: ServerConfig) -> list[str]:
        return [
            "gunicorn",
            "-w",
            str(config.workers),
            "-b",
            f"{config.host}:{config.port}",
            "-k",
            "uvicorn_worker.UvicornWorker",
            config.entry_point,
        ]

    def build_dev_command(self, config: ServerConfig) -> list[str]:
        return [
            "gunicorn",
            "-w",
            "1",
            "-b",
            f"{config.host}:{config.port}",
            "-k",
            "uvicorn_worker.UvicornWorker",
            "--reload",
            config.entry_point,
        ]

    def is_available(self) -> bool:
        return self.get_binary() is not None


class ServerRegistry:
    """Registry for server backends.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin backends.
    """

    def __init__(self) -> None:
        self._backends: dict[str, ServerBackend] = {}

    def register(self, backend: type[ServerBackend]) -> None:
        """Register a server backend class."""
        instance = backend()
        self._backends[backend.name] = instance

    def get(self, name: str) -> ServerBackend | None:
        """Get a backend by name."""
        return self._backends.get(name)

    def get_all(self) -> dict[str, ServerBackend]:
        """Get all registered backends."""
        return self._backends.copy()

    def get_available(self) -> list[ServerBackend]:
        """Get all available (installed) backends."""
        return [b for b in self._backends.values() if b.is_available()]

    def get_default(self) -> ServerBackend:
        """Get the default backend (prefer granian, then uvicorn, then first available)."""
        for preferred in ("granian", "uvicorn"):
            b = self._backends.get(preferred)
            if b and b.is_available():
                return b
        available = self.get_available()
        if available:
            return available[0]
        return self._backends["uvicorn"]

    @classmethod
    def _default_entries(cls) -> tuple[type[ServerBackend], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            UvicornBackend,
            HypercornBackend,
            GranianBackend,
            GunicornBackend,
        )

    @classmethod
    def with_defaults(cls) -> ServerRegistry:
        """Return an instance populated with the built-in backends."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


class ServerManager:
    """Manager for running ASGI servers."""

    def __init__(self, backend: ServerBackend | str | None = None) -> None:
        registry = ServerRegistry.with_defaults()
        if backend is None:
            self.backend = registry.get_default()
        elif isinstance(backend, str):
            backend_instance = registry.get(backend)
            if backend_instance is None:
                raise ValueError(f"Unknown server backend: {backend}")
            self.backend = backend_instance
        else:
            self.backend = backend

    def start(self, config: ServerConfig) -> None:
        """Start the server in production mode."""
        cmd = self.backend.build_start_command(config)
        env = os.environ.copy()
        env.update(config.env or {})
        env["QK_ENV"] = "production"

        try:
            subprocess.run(cmd, env=env, check=False)  # noqa: S603 — registry-built argv list
        except OSError as e:
            raise RuntimeError(f"Failed to start server: {e}") from e

    def start_dev(self, config: ServerConfig) -> None:
        """Start the server in development mode."""
        config.reload = True
        cmd = self.backend.build_dev_command(config)
        env = os.environ.copy()
        env.update(config.env or {})
        env["QK_ENV"] = "development"

        try:
            subprocess.run(cmd, env=env, check=False)  # noqa: S603 — registry-built argv list
        except OSError as e:
            raise RuntimeError(f"Failed to start dev server: {e}") from e


def discover_entry_point() -> str | None:
    """Discover application entry point from common locations."""
    candidates = [
        Path("src/main.py"),
        Path("main.py"),
        Path("app.py"),
        Path("src/app.py"),
    ]

    src_path = Path("src")
    if src_path.exists():
        candidates.extend(src_path.rglob("main.py"))
        candidates.extend(src_path.rglob("app.py"))

    for c in candidates:
        if c.exists():
            return str(c)
    return None


__all__ = [
    "GranianBackend",
    "GunicornBackend",
    "HypercornBackend",
    "ServerBackend",
    "ServerConfig",
    "ServerManager",
    "ServerRegistry",
    "UvicornBackend",
    "discover_entry_point",
]
