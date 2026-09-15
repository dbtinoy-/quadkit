"""Presets registry for application presets.

This module provides a registry pattern for application presets.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class Preset:
    """A preset configuration of providers."""

    name: str
    description: str
    packages: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


class PresetDefinition(abc.ABC):
    """Abstract base class for preset definitions."""

    name: ClassVar[str]
    description: ClassVar[str]
    packages: ClassVar[list[str]] = []
    config: ClassVar[dict[str, Any]] = {}

    @abc.abstractmethod
    def get_preset(self) -> Preset:
        """Get the preset configuration."""


class WebAPIPreset(PresetDefinition):
    """Basic web API preset."""

    name = "web-api"
    description = "Basic web API with HTTP routing and middleware"
    packages = ["quadkit", "quadkit-web", "quadkit-sql"]
    config = {
        "web": {"host": "0.0.0.0", "port": 8000},  # noqa: S104 — preset template default
        "database": {"url": "sqlite:///./dev.db"},
    }

    def get_preset(self) -> Preset:
        return Preset(
            name=self.name,
            description=self.description,
            packages=self.packages.copy(),
            config=self.config.copy(),
        )


class GraphQLPreset(PresetDefinition):
    """GraphQL API preset."""

    name = "graphql"
    description = "GraphQL API with web framework"
    packages = ["quadkit", "quadkit-web", "quadkit-sql", "quadkit-graphql"]
    config = {
        "web": {"host": "0.0.0.0", "port": 8000},  # noqa: S104 — preset template default
        "database": {"url": "sqlite:///./dev.db"},
        "graphql": {"path": "/graphql"},
    }

    def get_preset(self) -> Preset:
        return Preset(
            name=self.name,
            description=self.description,
            packages=self.packages.copy(),
            config=self.config.copy(),
        )


class WorkerPreset(PresetDefinition):
    """Background worker preset."""

    name = "worker"
    description = "Background job processor"
    packages = ["quadkit", "quadkit-sql", "quadkit-tasks", "quadkit-queue"]
    config = {
        "database": {"url": "sqlite:///./worker.db"},
    }

    def get_preset(self) -> Preset:
        return Preset(
            name=self.name,
            description=self.description,
            packages=self.packages.copy(),
            config=self.config.copy(),
        )


class FullStackPreset(PresetDefinition):
    """Full-stack application preset."""

    name = "fullstack"
    description = "Complete web application with database, auth, cache, and messaging"
    packages = [
        "quadkit",
        "quadkit-web",
        "quadkit-sql",
        "quadkit-auth",
        "quadkit-admin",
        "quadkit-cache",
        "quadkit-tasks",
        "quadkit-monitoring",
    ]
    config = {
        "web": {"host": "0.0.0.0", "port": 8000},  # noqa: S104 — preset template default
        "database": {"url": "sqlite:///./app.db"},
        "auth": {"enabled": True},
    }

    def get_preset(self) -> Preset:
        return Preset(
            name=self.name,
            description=self.description,
            packages=self.packages.copy(),
            config=self.config.copy(),
        )


class MinimalPreset(PresetDefinition):
    """Minimal preset."""

    name = "minimal"
    description = "Bare minimum Quadkit application"
    packages = ["quadkit"]
    config = {}

    def get_preset(self) -> Preset:
        return Preset(
            name=self.name,
            description=self.description,
            packages=self.packages.copy(),
            config=self.config.copy(),
        )


class MicroservicePreset(PresetDefinition):
    """Microservice preset."""

    name = "microservice"
    description = "Microservice with CQRS, database, and monitoring"
    packages = ["quadkit", "quadkit-sql", "quadkit-events", "quadkit-monitoring"]
    config = {
        "database": {"url": "sqlite:///./service.db"},
    }

    def get_preset(self) -> Preset:
        return Preset(
            name=self.name,
            description=self.description,
            packages=self.packages.copy(),
            config=self.config.copy(),
        )


class PresetRegistry:
    """Registry for application presets.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin presets.
    """

    def __init__(self) -> None:
        self._presets: dict[str, Preset] = {}

    def register(self, preset_class: type[PresetDefinition]) -> None:
        """Register a preset class."""
        instance = preset_class()
        preset = instance.get_preset()
        self._presets[preset.name] = preset

    def get(self, name: str) -> Preset | None:
        """Get a preset by name."""
        return self._presets.get(name)

    def get_all(self) -> dict[str, Preset]:
        """Get all registered presets."""
        return self._presets.copy()

    def get_choices(self) -> list[str]:
        """Get list of available preset names."""
        return list(self._presets.keys())

    @classmethod
    def _default_entries(cls) -> tuple[type[PresetDefinition], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            WebAPIPreset,
            GraphQLPreset,
            WorkerPreset,
            FullStackPreset,
            MinimalPreset,
            MicroservicePreset,
        )

    @classmethod
    def with_defaults(cls) -> PresetRegistry:
        """Return an instance populated with the built-in presets."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


__all__ = [
    "FullStackPreset",
    "GraphQLPreset",
    "MicroservicePreset",
    "MinimalPreset",
    "Preset",
    "PresetDefinition",
    "PresetRegistry",
    "WebAPIPreset",
    "WorkerPreset",
]
