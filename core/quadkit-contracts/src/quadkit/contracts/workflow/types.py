"""Value types for workflow orchestration contracts."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["StateTransitionRecord"]


@dataclass(frozen=True)
class StateTransitionRecord:
    """Immutable record of a persisted state transition.

    Attributes:
        machine_id: Stable identifier for the state machine instance.
        version: Monotonic transition version for optimistic locking.
        from_state: Source state name before the transition.
        event: Event name that triggered the transition.
        to_state: Destination state name after the transition.
        transitioned_at: UNIX timestamp (seconds) when transition was stored.
    """

    machine_id: str
    version: int
    from_state: str
    event: str
    to_state: str
    transitioned_at: float
