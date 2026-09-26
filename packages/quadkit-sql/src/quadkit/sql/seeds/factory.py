"""Factory pattern for generating test and seed entities.

Inspired by Laravel's Factories — provides a declarative way to
generate entities with fake data for tests and seeds.

Example:
    class UserFactory(Factory):
        __model__ = User

        def definition(self):
            return {
                "email": f"user{self._counter}@example.com",
                "name": f"User {self._counter}",
                "is_active": True,
            }

        def admin(self):
            return self.state("admin", {"role": "admin"})

    # Generate in-memory entities
    users = UserFactory().make(count=10)

    # Generate with overrides
    admin = UserFactory().admin().make_one(name="Super Admin")

This module provides standalone factory functions for creating components manually,
bypassing the internal Dependency Injection (DI) system and the `Application`
lifecycle.

WARNING: Use these factories ONLY when using this package as an independent,
standalone library. If you are inside a Quadkit `Application`, you MUST use
the DI Container to inject components instead of calling these factories directly.
This ensures inversion of control, proper lifecycle management, and testability.
"""

from __future__ import annotations

from typing import Any, TypeVar

from quadkit.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class Factory:
    """Factory for generating test/seed entities.

    Subclasses define a `definition()` method that returns
    default field values. Use `state()` to create variants.
    """

    __model__: type | None = None
    _global_counter: int = 0

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._active_states: list[str] = []
        self._counter = 0
        self._after_making: list[Any] = []
        self._sequences: dict[str, int] = {}

    def definition(self) -> dict[str, Any]:
        """Override to define default field values.

        Returns:
            Dictionary of field name → value.
        """
        return {}

    def state(self, name: str, overrides: dict[str, Any]) -> Factory:
        """Register a named state variant.

        Args:
            name: State name (e.g., "admin", "inactive").
            overrides: Field overrides for this state.

        Returns:
            self for chaining.
        """
        self._states[name] = overrides
        self._active_states.append(name)
        return self

    def make(
        self,
        count: int = 1,
        **overrides: Any,
    ) -> list[dict[str, Any]]:
        """Generate in-memory entities (not persisted).

        Args:
            count: Number of entities to generate.
            **overrides: Field overrides applied to all entities.

        Returns:
            List of entity dictionaries.
        """
        entities = []
        for _ in range(count):
            self._counter += 1
            Factory._global_counter += 1

            data = self.definition()

            # Apply active states
            for state_name in self._active_states:
                if state_name in self._states:
                    data.update(self._states[state_name])

            # Apply explicit overrides
            data.update(overrides)

            # Resolve callables
            for key, value in data.items():
                if callable(value):
                    data[key] = value()

            entities.append(data)

        # Reset active states after generation
        self._active_states = []
        return entities

    def make_one(self, **overrides: Any) -> dict[str, Any]:
        """Generate a single entity.

        Args:
            **overrides: Field overrides.

        Returns:
            Single entity dictionary.
        """
        results = self.make(count=1, **overrides)
        return results[0]

    def make_model(
        self,
        count: int = 1,
        **overrides: Any,
    ) -> list[Any]:
        """Generate model instances (if __model__ is set).

        Args:
            count: Number of entities.
            **overrides: Field overrides.

        Returns:
            List of model instances.
        """
        if not self.__model__:
            raise ValueError("__model__ not set on factory")

        dicts = self.make(count=count, **overrides)
        return [self.__model__(**d) for d in dicts]

    def sequence(self, name: str, start: int = 1) -> int:
        """Get next value in a named sequence.

        Args:
            name: Sequence name.
            start: Starting value (first call).

        Returns:
            Next integer in the sequence.
        """
        if name not in self._sequences:
            self._sequences[name] = start
        else:
            self._sequences[name] += 1
        return self._sequences[name]

    def reset_counter(self) -> None:
        """Reset the instance counter."""
        self._counter = 0

    @classmethod
    def reset_global_counter(cls) -> None:
        """Reset the global counter across all factories."""
        cls._global_counter = 0
