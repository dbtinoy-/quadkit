"""Configuration registry for Quadkit Framework."""

from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


class ConfigRegistry:
    """Registry for configuration extensions.

    Avoids global state by being instantiated per-application or per-provider.
    """

    def __init__(self) -> None:
        self._extensions: dict[str, type] = {}

    def register(self, name: str, config_class: type) -> None:
        """Register a configuration extension class.

        Args:
            name: Section name in the configuration.
            config_class: Pydantic model class for the section.
        """
        self._extensions[name] = config_class

    def get(self, name: str) -> type | None:
        """Get an extension class by name."""
        return self._extensions.get(name)

    def list_extensions(self) -> list[str]:
        """List all registered extension names."""
        return list(self._extensions.keys())

    def apply_to_instance(self, config_instance: Any) -> None:
        """Inject this registry into a configuration instance.

        This allows the instance to use the registry for dynamic section access.
        """
        if hasattr(config_instance, "_config_registry"):
            config_instance._config_registry = self
