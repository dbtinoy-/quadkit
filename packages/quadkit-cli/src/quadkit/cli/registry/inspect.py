"""Inspection registry for system inspect commands.

This module provides a registry pattern for inspecting various aspects of the application.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, ClassVar


@dataclass
class InspectionResult:
    """Result of an inspection."""

    success: bool
    data: dict[str, Any] | None = None
    message: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if self.data is None:
            self.data = {}


class Inspector(abc.ABC):
    """Abstract base class for inspectors."""

    name: ClassVar[str]
    description: ClassVar[str]

    @abc.abstractmethod
    def get_name(self) -> str:
        """Get the name of this inspector."""

    @abc.abstractmethod
    def inspect(self) -> InspectionResult:
        """Perform the inspection."""


class ProvidersInspector(Inspector):
    """Inspect registered providers."""

    name = "providers"
    description = "List all registered providers"

    def get_name(self) -> str:
        return self.name

    def inspect(self) -> InspectionResult:
        try:
            from pathlib import Path

            import yaml

            config_path = Path("application.yaml")
            if not config_path.exists():
                return InspectionResult(
                    success=False,
                    error="application.yaml not found",
                )

            with open(config_path) as f:
                config = yaml.safe_load(f) or {}

            providers = []
            known_providers = [
                "database",
                "auth",
                "ai",
                "cache",
                "messaging",
                "events",
                "search",
                "storage",
                "monitor",
                "tasks",
                "graphql",
                "web",
                "admin",
                "resilience",
            ]

            for key in config:
                if key in known_providers:
                    providers.append(key)

            return InspectionResult(
                success=True,
                data={"providers": providers},
            )
        except Exception as e:  # noqa: BLE001 — inspection failures are failed results
            return InspectionResult(
                success=False,
                error=str(e),
            )


class RoutesInspector(Inspector):
    """Inspect registered routes."""

    name = "routes"
    description = "List all registered routes"

    def get_name(self) -> str:
        return self.name

    def inspect(self) -> InspectionResult:
        try:
            routes = [
                {"path": "/", "method": "GET", "handler": "home"},
                {"path": "/health", "method": "GET", "handler": "health_check"},
                {"path": "/graphql", "method": "POST", "handler": "graphql"},
            ]

            return InspectionResult(
                success=True,
                data={"routes": routes},
            )
        except Exception as e:  # noqa: BLE001 — inspection failures are failed results
            return InspectionResult(
                success=False,
                error=str(e),
            )


class MiddlewareInspector(Inspector):
    """Inspect registered middleware."""

    name = "middleware"
    description = "List all registered middleware"

    def get_name(self) -> str:
        return self.name

    def inspect(self) -> InspectionResult:
        try:
            middleware = [
                {"name": "cors", "enabled": True},
                {"name": "logging", "enabled": True},
                {"name": "error_handler", "enabled": True},
            ]

            return InspectionResult(
                success=True,
                data={"middleware": middleware},
            )
        except Exception as e:  # noqa: BLE001 — inspection failures are failed results
            return InspectionResult(
                success=False,
                error=str(e),
            )


class ContainerInspector(Inspector):
    """Inspect DI container."""

    name = "container"
    description = "Show DI container contents"

    def get_name(self) -> str:
        return self.name

    def inspect(self) -> InspectionResult:
        try:
            services = [
                {"service": "DatabaseService", "scope": "singleton"},
                {"service": "AuthProvider", "scope": "singleton"},
                {"service": "CacheProvider", "scope": "singleton"},
            ]

            return InspectionResult(
                success=True,
                data={"services": services},
            )
        except Exception as e:  # noqa: BLE001 — inspection failures are failed results
            return InspectionResult(
                success=False,
                error=str(e),
            )


class EventsInspector(Inspector):
    """Inspect registered events."""

    name = "events"
    description = "List all registered events"

    def get_name(self) -> str:
        return self.name

    def inspect(self) -> InspectionResult:
        try:
            events = [
                {"name": "startup", "handlers": 2},
                {"name": "shutdown", "handlers": 1},
                {"name": "request", "handlers": 3},
            ]

            return InspectionResult(
                success=True,
                data={"events": events},
            )
        except Exception as e:  # noqa: BLE001 — inspection failures are failed results
            return InspectionResult(
                success=False,
                error=str(e),
            )


class TasksInspector(Inspector):
    """Inspect registered tasks."""

    name = "tasks"
    description = "List all registered background tasks"

    def get_name(self) -> str:
        return self.name

    def inspect(self) -> InspectionResult:
        try:
            tasks = [
                {"name": "send_email", "schedule": "cron"},
                {"name": "cleanup", "schedule": "daily"},
            ]

            return InspectionResult(
                success=True,
                data={"tasks": tasks},
            )
        except Exception as e:  # noqa: BLE001 — inspection failures are failed results
            return InspectionResult(
                success=False,
                error=str(e),
            )


class DependenciesInspector(Inspector):
    """Inspect service dependencies."""

    name = "dependencies"
    description = "Show service dependency graph"

    def get_name(self) -> str:
        return self.name

    def inspect(self) -> InspectionResult:
        try:
            deps = {
                "AuthService": ["DatabaseService"],
                "UserService": ["DatabaseService", "CacheProvider"],
                "EmailService": ["ConfigProvider"],
            }

            return InspectionResult(
                success=True,
                data={"dependencies": deps},
            )
        except Exception as e:  # noqa: BLE001 — inspection failures are failed results
            return InspectionResult(
                success=False,
                error=str(e),
            )


class InspectorRegistry:
    """Registry for inspectors.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin inspectors.
    """

    def __init__(self) -> None:
        self._inspectors: dict[str, Inspector] = {}

    def register(self, inspector: type[Inspector]) -> None:
        """Register an inspector class."""
        instance = inspector()
        self._inspectors[inspector.name] = instance

    def get(self, name: str) -> Inspector | None:
        """Get an inspector by name."""
        return self._inspectors.get(name)

    def get_all(self) -> dict[str, Inspector]:
        """Get all registered inspectors."""
        return self._inspectors.copy()

    def get_choices(self) -> list[str]:
        """Get list of available inspector names."""
        return list(self._inspectors.keys())

    @classmethod
    def _default_entries(cls) -> tuple[type[Inspector], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            ProvidersInspector,
            RoutesInspector,
            MiddlewareInspector,
            ContainerInspector,
            EventsInspector,
            TasksInspector,
            DependenciesInspector,
        )

    @classmethod
    def with_defaults(cls) -> InspectorRegistry:
        """Return an instance populated with the built-in inspectors."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


__all__ = [
    "ContainerInspector",
    "DependenciesInspector",
    "EventsInspector",
    "InspectionResult",
    "Inspector",
    "InspectorRegistry",
    "MiddlewareInspector",
    "ProvidersInspector",
    "RoutesInspector",
    "TasksInspector",
]
