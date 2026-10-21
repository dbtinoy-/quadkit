"""Presets registry for application presets.

This module provides a registry pattern for application presets.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, ClassVar

from quadkit.cli.package_names import packages_for


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


class ApiPreset(PresetDefinition):
    """The single application preset: REST API with the web framework."""

    name = "api"
    description = "REST API with the web framework"
    packages = packages_for("web")
    config = {
        "web": {"host": "0.0.0.0", "port": 8000},  # noqa: S104 — preset template default
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
        """Return the built-in presets (a single one today)."""
        return (ApiPreset,)

    @classmethod
    def with_defaults(cls) -> PresetRegistry:
        """Return an instance populated with the built-in presets."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


__all__ = [
    "ApiPreset",
    "Preset",
    "PresetDefinition",
    "PresetRegistry",
]
