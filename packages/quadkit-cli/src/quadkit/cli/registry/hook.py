"""Hook registry for CLI lifecycle events.

This module provides a registry pattern for CLI hooks/middleware.
"""

from __future__ import annotations

import abc
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HookPhase(str, Enum):
    """Phase of CLI execution."""

    PRE_STARTUP = "pre_startup"
    POST_STARTUP = "post_startup"
    PRE_SHUTDOWN = "pre_shutdown"
    POST_SHUTDOWN = "post_shutdown"
    PRE_COMMAND = "pre_command"
    POST_COMMAND = "post_command"
    PRE_ERROR = "pre_error"
    POST_ERROR = "post_error"


@dataclass
class HookContext:
    """Context passed to hooks."""

    command: str = ""
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    result: Any = None
    error: Exception | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class HookResult:
    """Result of hook execution."""

    success: bool
    message: str = ""
    modified_context: HookContext | None = None


HookHandler = Callable[[HookContext], Awaitable[HookResult]]


class Hook(abc.ABC):
    """Abstract base class for hooks."""

    name: str
    phase: HookPhase
    priority: int = 100

    @abc.abstractmethod
    async def execute(self, context: HookContext) -> HookResult:
        """Execute the hook."""

    def should_run(self, context: HookContext) -> bool:
        """Determine if this hook should run."""
        return True


class LoggingHook(Hook):
    """Hook for logging commands."""

    name = "logging"
    phase = HookPhase.PRE_COMMAND
    priority = 50

    async def execute(self, context: HookContext) -> HookResult:
        return HookResult(success=True)


class TimingHook(Hook):
    """Hook for timing command execution."""

    name = "timing"
    phase = HookPhase.PRE_COMMAND
    priority = 10

    async def execute(self, context: HookContext) -> HookResult:
        import time

        context.metadata["start_time"] = time.time()
        return HookResult(success=True)


class ErrorHandlingHook(Hook):
    """Hook for error handling."""

    name = "error_handler"
    phase = HookPhase.PRE_ERROR
    priority = 50

    async def execute(self, context: HookContext) -> HookResult:
        if context.error:
            return HookResult(success=False, message=str(context.error))
        return HookResult(success=True)


class ValidationHook(Hook):
    """Hook for command validation."""

    name = "validator"
    phase = HookPhase.PRE_COMMAND
    priority = 20

    def __init__(self, validator_fn: Callable[[HookContext], bool]):
        self.validator_fn = validator_fn

    async def execute(self, context: HookContext) -> HookResult:
        if self.validator_fn(context):
            return HookResult(success=True)
        return HookResult(success=False, message="Validation failed")


class HookRegistry:
    """Registry for CLI hooks.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin hooks.
    """

    def __init__(self) -> None:
        self._hooks: dict[HookPhase, list[Hook]] = {}

    def register(self, hook: Hook) -> None:
        """Register a hook."""
        if hook.phase not in self._hooks:
            self._hooks[hook.phase] = []
        self._hooks[hook.phase].append(hook)
        self._hooks[hook.phase].sort(key=lambda h: h.priority)

    def register_class(self, hook_class: type[Hook]) -> None:
        """Register a hook class."""
        instance = hook_class()
        self.register(instance)

    def get_hooks(self, phase: HookPhase) -> list[Hook]:
        """Get hooks for a specific phase."""
        return self._hooks.get(phase, []).copy()

    def get_all_hooks(self) -> dict[HookPhase, list[Hook]]:
        """Get all registered hooks."""
        return self._hooks.copy()

    @classmethod
    def _default_entries(cls) -> tuple[Hook, ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            LoggingHook(),
            TimingHook(),
            ErrorHandlingHook(),
        )

    @classmethod
    def with_defaults(cls) -> HookRegistry:
        """Return an instance populated with the built-in hooks."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


class HookExecutor:
    """Executes hooks for CLI lifecycle events."""

    def __init__(self) -> None:
        self.registry = HookRegistry.with_defaults()

    async def execute_phase(
        self,
        phase: HookPhase,
        context: HookContext,
    ) -> HookContext:
        """Execute all hooks for a phase."""
        hooks = self.registry.get_hooks(phase)

        for hook in hooks:
            if not hook.should_run(context):
                continue

            try:
                result = await hook.execute(context)
                if not result.success:
                    context.metadata["hook_error"] = result.message

                if result.modified_context:
                    context = result.modified_context

            except Exception as e:  # noqa: BLE001 — hook failures are recorded in context metadata
                context.metadata["hook_error"] = str(e)

        return context

    async def pre_command(self, command: str, args: tuple, kwargs: dict) -> HookContext:
        """Execute pre-command hooks."""
        context = HookContext(command=command, args=args, kwargs=kwargs)
        return await self.execute_phase(HookPhase.PRE_COMMAND, context)

    async def post_command(self, context: HookContext, result: Any) -> HookContext:
        """Execute post-command hooks."""
        context.result = result
        return await self.execute_phase(HookPhase.POST_COMMAND, context)

    async def on_error(self, context: HookContext, error: Exception) -> HookContext:
        """Execute error hooks."""
        context.error = error
        return await self.execute_phase(HookPhase.PRE_ERROR, context)


def create_validation_hook(
    name: str,
    validator: Callable[[HookContext], bool],
    phase: HookPhase = HookPhase.PRE_COMMAND,
    priority: int = 20,
) -> Hook:
    """Create a validation hook from a function."""

    class CustomValidationHook(Hook):
        def __init__(self) -> None:
            super().__init__()
            self.name = name
            self.phase = phase
            self.priority = priority
            self.validator = validator

        async def execute(self, context: HookContext) -> HookResult:
            if self.validator(context):
                return HookResult(success=True)
            return HookResult(success=False, message=f"Validation failed: {name}")

    return CustomValidationHook()


__all__ = [
    "ErrorHandlingHook",
    "Hook",
    "HookContext",
    "HookExecutor",
    "HookHandler",
    "HookPhase",
    "HookRegistry",
    "HookResult",
    "LoggingHook",
    "TimingHook",
    "ValidationHook",
    "create_validation_hook",
]
