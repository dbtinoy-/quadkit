"""Action lifecycle hook contracts — before/after/failure hooks for admin actions.

Defines the ``ActionHookProtocol`` that action-level and resource-level
hooks must satisfy, plus the ``HasActionHooks`` protocol marking objects
that expose hook collections.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.admin.errors import AdminError
    from quadkit.contracts.core.result import Result


@runtime_checkable
class ActionHookProtocol(Protocol):
    """Lifecycle hooks for admin actions.

    Hooks are executed around the action body by ``ActionExecutor``:

    - ``before()`` runs first and may modify the input data or abort the
      action by returning ``Err``.
    - ``after()`` runs after successful execution.
    - ``on_failure()`` runs when ``before()`` returned ``Err`` or the
      action body raised an exception.
    """

    async def before(
        self, record: Any, data: dict[str, Any]
    ) -> Result[dict[str, Any], AdminError]:
        """Run before the action body.

        Args:
            record: The target record (may be ``None`` for global actions).
            data: Action payload; may be amended by the hook.

        Returns:
            ``Ok(data)`` with possibly-amended data, or ``Err`` to abort.
        """
        ...

    async def after(self, record: Any, result: Any) -> None:
        """Run after a successful action execution.

        Args:
            record: The target record (may be ``None`` for global actions).
            result: The action result payload.
        """
        ...

    async def on_failure(self, record: Any, error: Exception) -> None:
        """Run when the action fails.

        Args:
            record: The target record (may be ``None`` for global actions).
            error: The exception or error that caused the failure.
        """
        ...


@runtime_checkable
class HasActionHooks(Protocol):
    """Protocol for objects exposing action lifecycle hooks.

    Implemented by action handlers and resources so the executor can
    discover ``before`` / ``after`` / ``failure`` hooks declaratively.
    """

    @property
    def before_hooks(self) -> list[ActionHookProtocol]:
        """Hooks run before the action body."""
        ...

    @property
    def after_hooks(self) -> list[ActionHookProtocol]:
        """Hooks run after successful execution."""
        ...

    @property
    def failure_hooks(self) -> list[ActionHookProtocol]:
        """Hooks run on action failure."""
        ...


__all__ = ["ActionHookProtocol", "HasActionHooks"]
