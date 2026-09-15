"""Task runner registry for project commands.

This module provides a registry pattern for task runners (test, lint, etc).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
import shutil
import subprocess
from typing import Any, ClassVar


@dataclass
class TaskResult:
    """Result of a task execution."""

    success: bool
    message: str = ""
    output: str = ""
    exit_code: int = 0


class TaskRunner(abc.ABC):
    """Abstract base class for task runners."""

    name: ClassVar[str]
    description: ClassVar[str]

    @abc.abstractmethod
    def get_name(self) -> str:
        """Get the name of this task runner."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check if the required tools are available."""

    @abc.abstractmethod
    def run(self, **options: Any) -> TaskResult:
        """Run the task."""


class PytestRunner(TaskRunner):
    """Pytest test runner."""

    name = "pytest"
    description = "Run project tests"

    def get_name(self) -> str:
        return self.name

    def is_available(self) -> bool:
        return shutil.which("pytest") is not None

    def run(
        self,
        path: str = ".",
        coverage: bool = False,
        verbose: bool = False,
        **options: Any,
    ) -> TaskResult:
        cmd = ["pytest", path]
        if coverage:
            cmd.extend(["--cov=src", "--cov-report=term-missing"])
        if verbose:
            cmd.append("-v")

        try:
            result = subprocess.run(  # noqa: S603 — argv list, no shell; operator-supplied path arg
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
            return TaskResult(
                success=result.returncode == 0,
                output=result.stdout + result.stderr,
                exit_code=result.returncode,
            )
        except Exception as e:  # noqa: BLE001 — task failures are failed results
            return TaskResult(
                success=False,
                message=f"Failed to run pytest: {e}",
            )


class RuffRunner(TaskRunner):
    """Ruff linter runner."""

    name = "ruff"
    description = "Run project linting"

    def get_name(self) -> str:
        return self.name

    def is_available(self) -> bool:
        return shutil.which("ruff") is not None

    def run(
        self,
        path: str = ".",
        fix: bool = False,
        **options: Any,
    ) -> TaskResult:
        cmd = ["ruff", "check", path]
        if fix:
            cmd.append("--fix")

        try:
            result = subprocess.run(  # noqa: S603 — argv list, no shell; operator-supplied path arg
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
            return TaskResult(
                success=result.returncode == 0,
                output=result.stdout + result.stderr,
                exit_code=result.returncode,
            )
        except Exception as e:  # noqa: BLE001 — task failures are failed results
            return TaskResult(
                success=False,
                message=f"Failed to run ruff: {e}",
            )


class MypyRunner(TaskRunner):
    """Mypy type checker runner."""

    name = "mypy"
    description = "Run type checking"

    def get_name(self) -> str:
        return self.name

    def is_available(self) -> bool:
        return shutil.which("mypy") is not None

    def run(
        self,
        path: str = "src",
        **options: Any,
    ) -> TaskResult:
        cmd = ["mypy", path]

        try:
            result = subprocess.run(  # noqa: S603 — argv list, no shell; operator-supplied path arg
                cmd,
                check=False,
                capture_output=True,
                text=True,
            )
            return TaskResult(
                success=result.returncode == 0,
                output=result.stdout + result.stderr,
                exit_code=result.returncode,
            )
        except Exception as e:  # noqa: BLE001 — task failures are failed results
            return TaskResult(
                success=False,
                message=f"Failed to run mypy: {e}",
            )


class TaskRunnerRegistry:
    """Registry for task runners.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin runners.
    """

    def __init__(self) -> None:
        self._runners: dict[str, TaskRunner] = {}

    def register(self, runner: type[TaskRunner]) -> None:
        """Register a task runner class."""
        instance = runner()
        self._runners[runner.name] = instance

    def get(self, name: str) -> TaskRunner | None:
        """Get a runner by name."""
        return self._runners.get(name)

    def get_all(self) -> dict[str, TaskRunner]:
        """Get all registered runners."""
        return self._runners.copy()

    def get_available(self) -> list[TaskRunner]:
        """Get all available (installed) runners."""
        return [r for r in self._runners.values() if r.is_available()]

    @classmethod
    def _default_entries(cls) -> tuple[type[TaskRunner], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            PytestRunner,
            RuffRunner,
            MypyRunner,
        )

    @classmethod
    def with_defaults(cls) -> TaskRunnerRegistry:
        """Return an instance populated with the built-in runners."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


__all__ = [
    "MypyRunner",
    "PytestRunner",
    "RuffRunner",
    "TaskResult",
    "TaskRunner",
    "TaskRunnerRegistry",
]
