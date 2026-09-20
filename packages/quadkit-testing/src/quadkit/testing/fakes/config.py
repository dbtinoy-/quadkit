"""Fake configuration source for injecting test values without real config files."""

from __future__ import annotations

from typing import Any, cast

__all__ = ["FakeConfig"]


class FakeConfig:
    """In-memory config satisfying a ``ConfigProtocol``-like interface.

    Supports dot-notation key access (``"database.url"``) and optional
    section retrieval with model instantiation.

    Example::

        config = FakeConfig({"database": {"url": "sqlite:///:memory:"}})
        assert config.get("database.url") == "sqlite:///:memory:"
        config.set("cache.backend", "memory")
    """

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = data or {}

    @property
    def environment(self) -> Any:
        """The active deployment environment (returns test environment)."""
        from quadkit.contracts.core.config import Environment

        return Environment.TEST

    @property
    def is_debug(self) -> bool:
        """Return False for test environments."""
        return False

    @property
    def is_production(self) -> bool:
        """Return False for test environments."""
        return cast("bool", self.environment.value == "production")

    @property
    def is_development(self) -> bool:
        """Return whether this is development."""
        return cast("bool", self.environment.value == "development")

    @property
    def is_testing(self) -> bool:
        """Return whether this is testing."""
        return cast("bool", self.environment.value == "test")

    @property
    def is_staging(self) -> bool:
        """Return whether this is staging."""
        return cast("bool", self.environment.value == "staging")

    def has_section(self, name: str) -> bool:
        """Check whether a configuration section exists."""
        return name in self._data and isinstance(self._data[name], dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve *key* from config, returning *default* if absent.

        A literal key (e.g. ``"feature.enabled"`` stored as-is) wins over
        dot-traversal, so both flat and nested data layouts work.
        """
        if key in self._data:
            return self._data[key]
        parts = key.split(".")
        current: Any = self._data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current

    def get_section(self, name: str, model_cls: type | None = None) -> Any:
        """Return the config section *name*, optionally instantiated as *model_cls*."""
        section = self._data.get(name, {})
        if model_cls is not None:
            return model_cls(**section)
        return section

    def set(self, key: str, value: Any) -> None:
        """Set *key* (dot-separated path) to *value* — test-only helper."""
        parts = key.split(".")
        current: Any = self._data
        for part in parts[:-1]:
            if not isinstance(current, dict):
                break
            current = current.setdefault(part, {})
        if isinstance(current, dict):
            current[parts[-1]] = value
