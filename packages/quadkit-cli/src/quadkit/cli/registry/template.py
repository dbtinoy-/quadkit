"""Project template registry for the new command.

This module provides a registry pattern for project templates.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from quadkit.cli.package_names import packages_for, provider_available

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class TemplateConfig:
    """Configuration for a project template."""

    name: str
    description: str = ""
    packages: list[str] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)


class ProjectTemplate(abc.ABC):
    """Abstract base class for project templates."""

    name: ClassVar[str]
    description: ClassVar[str]
    packages: ClassVar[list[str]] = []
    files: ClassVar[dict[str, str]] = {}

    @abc.abstractmethod
    def get_config(self) -> TemplateConfig:
        """Get the template configuration."""

    def get_dependencies(self) -> list[str]:
        """Get the list of dependencies for this template."""
        return self.packages.copy()


class MinimalTemplate(ProjectTemplate):
    """Minimal template with just the core framework."""

    name = "minimal"
    description = "Bare minimum Quadkit application"
    packages = [
        "quadkit",
    ]

    def get_config(self) -> TemplateConfig:
        return TemplateConfig(
            name=self.name,
            description=self.description,
            packages=self.packages,
        )


class WebAPITemplate(ProjectTemplate):
    """REST API template."""

    name = "web-api"
    description = "REST API with web framework"
    packages = packages_for("web", "sql")

    def get_config(self) -> TemplateConfig:
        return TemplateConfig(
            name=self.name,
            description=self.description,
            packages=self.packages,
        )


class GraphQLTemplate(ProjectTemplate):
    """GraphQL API template."""

    name = "graphql"
    description = "GraphQL API with web framework"
    packages = packages_for("web", "sql", "graphql")

    def get_config(self) -> TemplateConfig:
        return TemplateConfig(
            name=self.name,
            description=self.description,
            packages=self.packages,
        )


class WorkerTemplate(ProjectTemplate):
    """Background worker template."""

    name = "worker"
    description = "Background job processor"
    packages = packages_for("sql", "tasks", "queue")

    def get_config(self) -> TemplateConfig:
        return TemplateConfig(
            name=self.name,
            description=self.description,
            packages=self.packages,
        )


class FullStackTemplate(ProjectTemplate):
    """Full-stack application template."""

    name = "fullstack"
    description = "Full application with auth, admin, and more"
    packages = packages_for("web", "sql", "auth", "admin", "cache", "tasks", "monitor")

    def get_config(self) -> TemplateConfig:
        return TemplateConfig(
            name=self.name,
            description=self.description,
            packages=self.packages,
        )


class TemplateRegistry:
    """Registry for project templates.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin templates.
    """

    def __init__(self) -> None:
        self._templates: dict[str, ProjectTemplate] = {}

    def register(self, template: type[ProjectTemplate]) -> None:
        """Register a project template class."""
        instance = template()
        self._templates[template.name] = instance

    def get(self, name: str) -> ProjectTemplate | None:
        """Get a template by name."""
        return self._templates.get(name)

    def get_all(self) -> dict[str, ProjectTemplate]:
        """Get all registered templates."""
        return self._templates.copy()

    def get_choices(self) -> list[str]:
        """Get list of available template names."""
        return list(self._templates.keys())

    @classmethod
    def _default_entries(cls) -> tuple[type[ProjectTemplate], ...]:
        """Return templates supported by installed optional providers."""
        entries: list[type[ProjectTemplate]] = [MinimalTemplate, WebAPITemplate]
        optional = (
            (GraphQLTemplate, ("sql", "graphql")),
            (WorkerTemplate, ("sql", "tasks", "queue")),
            (FullStackTemplate, ("web", "sql", "auth", "admin", "cache", "tasks")),
        )
        for entry, features in optional:
            if all(provider_available(feature) for feature in features):
                entries.append(entry)
        return tuple(entries)

    @classmethod
    def with_defaults(cls) -> TemplateRegistry:
        """Return an instance populated with the built-in templates."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


class ProjectBuilder:
    """Builder for creating new projects from templates.

    Delegates to the canonical :mod:`quadkit.cli.scaffold` renderer so the
    registry templates and ``quadkit new project --template`` produce the
    exact same, fully aligned project tree.
    """

    def __init__(self, template: ProjectTemplate | str):
        if isinstance(template, str):
            resolved = TemplateRegistry.with_defaults().get(template)
            if resolved is None:
                raise ValueError(f"Unknown template: {template}")
            self.template = resolved
        else:
            self.template = template

    def create_project(
        self,
        project_name: str,
        target_dir: Path,
        options: dict[str, Any] | None = None,
    ) -> list[Path]:
        """Create a new project from the template.

        Args:
            project_name: Project name (dashes become underscores).
            target_dir: Destination directory.
            options: Reserved for feature toggles (currently unused).

        Returns:
            The list of created file paths.

        Raises:
            ValueError: Directory is not empty or the template is unknown.
        """
        from quadkit.cli.scaffold import render_project

        return render_project(self.template.name, project_name, target_dir)


__all__ = [
    "FullStackTemplate",
    "GraphQLTemplate",
    "MinimalTemplate",
    "ProjectBuilder",
    "ProjectTemplate",
    "TemplateConfig",
    "TemplateRegistry",
    "WebAPITemplate",
    "WorkerTemplate",
]
