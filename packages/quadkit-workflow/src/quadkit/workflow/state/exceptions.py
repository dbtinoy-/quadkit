"""State machine exceptions."""

from __future__ import annotations

from quadkit.contracts.exceptions import ConflictError

__all__ = [
    "StateConcurrencyError",
    "StateError",
    "StateVersionConflictError",
]


class StateVersionConflictError(RuntimeError):
    """Persistence-layer signal that an optimistic version check failed.

    A ``RuntimeError`` subclass so it satisfies the contracts
    ``StatePersistenceProtocol.append_transition`` documented raise, while
    giving callers (``StateMachine``) a *typed* conflict signal — other
    ``RuntimeError``s (driver/DDL failures) are no longer misread as
    version conflicts.
    """

    def __init__(
        self,
        message: str,
        *,
        expected_version: int,
        actual_version: int,
    ) -> None:
        super().__init__(message)
        self.expected_version = expected_version
        self.actual_version = actual_version


class StateError(ConflictError):
    """Raised when an invalid state transition is attempted.

    Extends the contracts ``ConflictError`` (a ``DomainError``): an illegal
    transition conflicts with the aggregate's current state, so HTTP layers
    map it to 409 automatically via ``ResultResponseMapper`` — no manual
    registration needed.

    Attributes:
        event: The event that was not permitted.
        current_state: The state the machine was in when the error occurred.
    """

    _code: str = "QK_ERR_WF_017"

    def __init__(self, event: str, current_state: str) -> None:
        super().__init__("The requested state transition is not permitted.")
        self.event = event
        self.current_state = current_state


class StateConcurrencyError(StateError):
    """Raised when optimistic version checks fail during a transition.

    Also a conflict (409): the write collided with a concurrent version bump.
    """

    _code: str = "QK_ERR_WF_018"

    def __init__(
        self,
        event: str,
        current_state: str,
        expected_version: int,
        actual_version: int,
    ) -> None:
        super().__init__(event=event, current_state=current_state)
        self.expected_version = expected_version
        self.actual_version = actual_version
        self.message = "State transition conflicts with the current version."
