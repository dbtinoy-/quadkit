"""CLI contribution types for the expanded contributor protocol."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class CommandContribution:
    """A CLI command group contributed by an extension package.

    The ``app_factory_path`` points to a function that returns a
    ``typer.Typer`` instance containing all subcommands for this group.
    The format is ``"module.path:callable_name"``.
    """

    name: str
    help: str
    app_factory_path: str
    contributor: str
    category: str = "extension"
    hidden: bool = False
    requires_app_context: bool = False


@dataclass(frozen=True)
class HealthCheckContribution:
    """A runtime health check contributed by an extension package.

    The ``check_path`` points to an async function with signature:
    ``async def check(container) -> HealthCheckResult``
    The format is ``"module.path:function_name"``.
    """

    name: str
    description: str
    check_path: str
    contributor: str
    category: str = "general"
    timeout: float = 10.0
    critical: bool = False


@dataclass(frozen=True)
class DoctorCheckContribution:
    """An environment/config diagnostic check contributed by an extension.

    The ``check_path`` points to a sync function with signature:
    ``def check() -> DoctorCheckResult``
    The format is ``"module.path:function_name"``.
    """

    name: str
    description: str
    check_path: str
    contributor: str
    category: str = "general"
    can_fix: bool = False


@dataclass(frozen=True)
class ShellContextContribution:
    """An object to inject into the interactive shell namespace.

    The ``factory_path`` points to an async function with signature:
    ``async def factory(container) -> Any``
    The format is ``"module.path:function_name"``.
    """

    name: str
    description: str
    factory_path: str
    contributor: str


@dataclass(frozen=True)
class HookContribution:
    """A CLI lifecycle hook contributed by an extension package.

    The ``handler_path`` points to a callable with signature:
    ``def handler(ctx) -> None`` or ``async def handler(ctx) -> None``
    The format is ``"module.path:function_name"``.
    """

    event: str
    handler_path: str
    contributor: str
    priority: int = 50


class SchemaSetupResult(str, Enum):
    """Outcome status of a schema setup contribution's ensure() call."""

    CREATED = "created"
    ALREADY_PRESENT = "already_present"
    FAILED = "failed"


@dataclass(frozen=True)
class SchemaSetupOutcome:
    """Result of running a single SchemaSetupContribution's ensure() callable."""

    status: SchemaSetupResult
    message: str | None = None


@dataclass(frozen=True)
class SchemaSetupContribution:
    """A database schema setup step contributed by an extension package.

    The ``setup_fn_path`` points to an async function with signature:
    ``async def ensure(db: DatabaseProviderProtocol) -> SchemaSetupOutcome``
    The format is ``"module.path:function_name"``.
    """

    name: str
    description: str
    setup_fn_path: str
    contributor: str
    category: str = "general"


__all__ = [
    "CommandContribution",
    "DoctorCheckContribution",
    "HealthCheckContribution",
    "HookContribution",
    "SchemaSetupContribution",
    "SchemaSetupOutcome",
    "SchemaSetupResult",
    "ShellContextContribution",
]
