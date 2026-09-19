"""Unified Builder foundation for Quadkit Framework.

Providing a standardized way to construct complex objects with a fluent API,
supporting both manual builder implementation and automatic builder generation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import copy
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar, get_type_hints

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


class AbstractBuilder(ABC, Generic[T]):
    """Base class for all fluent builders in Quadkit.

    Provides foundational support for state management and fluent chaining.
    """

    def __init__(self) -> None:
        """Initialize builder state."""
        # State is typically stored in protected attributes in subclasses

    def copy(self) -> Self:
        """Return a deep copy of the builder state.

        Useful for creating slightly different variations of an object
        without rebuilding from scratch.
        """
        return copy.deepcopy(self)

    @abstractmethod
    def build(self) -> T:
        """Construct the final object from the builder state.

        Returns:
            The constructed object of type T.
        """
        ...


def builder_field(field_or_func: str | Callable[..., Any]) -> Callable[..., Any]:
    """Decorator or helper to define builder methods.

    Can be used as a decorator on a method to mark it as a builder field,
    or as a metadata marker for automated builder generation.
    """
    if callable(field_or_func):
        # Used as decorator
        func = field_or_func
        func.__is_builder_field__ = True  # type: ignore[attr-defined]
        return func

    # Used with field name (less common, usually for auto-gen)
    return field_or_func  # type: ignore[return-value]


def buildable(cls: type[T]) -> type[T]:
    """Class decorator that auto-generates a fluent Builder for the decorated class.

    Introspects ``__init__`` to discover parameters and generates
    ``with_<param>()`` setter methods on a dynamically created builder.
    Required parameters (those without defaults) are validated at
    ``build()`` time and raise ``TypeError`` if missing.

    Adds a ``.builder()`` class method that returns a fresh builder
    instance each time it is called.

    Example::

        @buildable
        class User:
            def __init__(self, name: str, email: str, age: int = 0):
                self.name = name
                self.email = email
                self.age = age

        user = (
            User.builder()
            .with_name("John")
            .with_email("john@example.com")
            .with_age(30)
            .build()
        )

    Args:
        cls: The class to decorate.  Must have a standard ``__init__``
            with type-annotated parameters.

    Returns:
        The same class with an attached ``.builder()`` static method.
    """

    class GeneratedBuilder(AbstractBuilder[T]):
        def __init__(self) -> None:
            super().__init__()
            self._params: dict[str, Any] = {}

            # Discover required params (no default) from __init__
            import inspect

            sig = inspect.signature(cls.__init__)
            self._required_params: list[str] = []
            for name, param in sig.parameters.items():
                if name == "self":
                    continue
                if param.default is inspect.Parameter.empty and param.kind in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                ):
                    self._required_params.append(name)

        def build(self) -> T:
            missing = [p for p in self._required_params if p not in self._params]
            if missing:
                raise TypeError(
                    f"{cls.__name__}() missing required arguments: {', '.join(missing)}",
                )
            return cls(**self._params)

    def builder() -> GeneratedBuilder:
        return GeneratedBuilder()

    # Add builder method to class
    cls.builder = staticmethod(builder)  # type: ignore[attr-defined]

    # Dynamically add with_ methods
    hints = get_type_hints(cls.__init__)
    for param_name in hints:
        if param_name == "return":
            continue

        def create_with_method(name: str) -> GeneratedBuilder:
            def with_method(self: GeneratedBuilder, value: Any) -> GeneratedBuilder:
                self._params[name] = value
                return self

            return with_method  # type: ignore[return-value]

        setattr(GeneratedBuilder, f"with_{param_name}", create_with_method(param_name))

    return cls
