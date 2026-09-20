"""Code generator registry for the gen command.

This module provides a registry pattern for code generators and a
contract-aligned, instance-based GeneratorRegistry.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from importlib import import_module
from typing import Any, ClassVar

from quadkit.contracts.cli.types import GeneratorDefinition


@dataclass
class GeneratorResult:
    """Result of a code generation operation."""

    success: bool
    files_created: list[str] | None = None
    files_updated: list[str] | None = None
    message: str = ""
    error: str = ""

    def __post_init__(self) -> None:
        if self.files_created is None:
            self.files_created = []
        if self.files_updated is None:
            self.files_updated = []


class CodeGenerator(abc.ABC):
    """Abstract base class for code generators."""

    name: ClassVar[str]
    description: ClassVar[str]
    default_output_dir: ClassVar[str] = "src"

    @abc.abstractmethod
    def get_name(self) -> str:
        """Get the name of this generator."""

    @abc.abstractmethod
    def get_description(self) -> str:
        """Get the description of this generator."""

    @abc.abstractmethod
    def generate(
        self,
        name: str,
        output_dir: str = "src",
        **options: Any,
    ) -> GeneratorResult:
        """Generate code."""

    def get_options(self) -> dict[str, Any]:
        """Get default options for this generator."""
        return {}


class GeneratorAdapter(CodeGenerator):
    """Adapter to wrap existing generator classes for the registry."""

    def __init__(
        self,
        generator_class: type,
        default_output: str = "src",
        description: str | None = None,
    ) -> None:
        self._generator_class = generator_class
        self._default_output = default_output
        self._description = description

    def get_name(self) -> str:
        cls = self._generator_class
        class_name: Any = getattr(cls, "name", None)
        if class_name:
            return str(class_name)
        return cls.__name__.replace("Generator", "").lower()

    def get_description(self) -> str:
        if self._description is not None:
            return self._description
        return f"Generate {self.get_name()}"

    def generate(
        self,
        name: str,
        output_dir: str = "src",
        **options: Any,
    ) -> GeneratorResult:
        try:
            generator = self._generator_class(output_dir=output_dir)
            result = generator.generate(name, **options)
            return GeneratorResult(
                success=True,
                files_created=[str(file_path) for file_path in result.files_created],
                files_updated=[
                    str(file_path) for file_path in result.files_overwritten
                ],
                message=f"Generated {len(result.files_created)} files",
            )
        except Exception as error:  # noqa: BLE001 — any generation failure is a failed result
            return GeneratorResult(success=False, error=str(error))

    def get_default_output_dir(self) -> str:
        """Return the configured default output directory."""
        return self._default_output


class GeneratorRegistry:
    """Registry for CLI generator definitions contributed by CliContributors.

    Instances are populated exclusively through contributor discovery
    (:func:`quadkit.cli.contributors.discovery.populate_cli_registries`) —
    the generator set is plugin-defined (entry points across packages), so
    there is no static built-in set and therefore no ``with_defaults()``.
    """

    def __init__(self) -> None:
        self._generators: dict[str, GeneratorDefinition] = {}

    def register(self, generator: GeneratorDefinition) -> None:
        """Register a generator definition."""
        self._generators[generator.name] = generator

    def get(self, name: str) -> GeneratorDefinition | None:
        """Look up a generator by name."""
        return self._generators.get(name)

    def get_adapter(self, name: str) -> GeneratorAdapter | None:
        """Resolve a generator adapter from a registered module:path string."""
        definition = self.get(name)
        if definition is None:
            return None
        generator_class = self._load_generator_class(definition.generator_path)
        return GeneratorAdapter(
            generator_class,
            default_output=definition.default_output_dir,
            description=definition.description,
        )

    def list_generators(self) -> list[GeneratorDefinition]:
        """Return all registered generators in insertion order."""
        return list(self._generators.values())

    @staticmethod
    def _load_generator_class(generator_path: str) -> type:
        """Load a generator class from a ``module:path`` string."""
        module_path, separator, attribute_path = generator_path.partition(":")
        if not separator or not module_path or not attribute_path:
            raise ValueError("generator_path must use the module.path:ClassName format")
        module = import_module(module_path)
        resolved: object = module
        for attribute_name in attribute_path.split("."):
            resolved = getattr(resolved, attribute_name)
        if not isinstance(resolved, type):
            raise TypeError(f"Generator path must resolve to a class: {generator_path}")
        return resolved


__all__ = [
    "CodeGenerator",
    "GeneratorAdapter",
    "GeneratorRegistry",
    "GeneratorResult",
]
