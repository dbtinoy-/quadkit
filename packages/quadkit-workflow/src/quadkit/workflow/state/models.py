"""State and Transition dataclasses for the state machine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

__all__ = ["State", "Transition"]


@dataclass
class Transition:
    """A permitted transition between two states.

    Attributes:
        event: The event name that triggers this transition.
        target: The name of the destination state.
        guard: Optional async callable that must return ``True`` for the
            transition to proceed.  When ``None``, the transition is
            unconditional.
        on_transition: Optional async callback invoked after the state
            changes.  Receives the event name and the new state name.
    """

    event: str
    target: str
    guard: Callable[[], Awaitable[bool]] | None = None
    on_transition: Callable[[str, str], Awaitable[None]] | None = None


@dataclass
class State:
    """A node in the state machine graph.

    Attributes:
        name: Unique name identifying this state.
        transitions: Permitted outgoing transitions keyed by event name.
        on_enter: Optional async callback invoked when the machine enters
            this state.
        on_exit: Optional async callback invoked when the machine leaves
            this state.
    """

    name: str
    transitions: dict[str, Transition] = field(default_factory=dict)
    on_enter: Callable[[], Awaitable[None]] | None = None
    on_exit: Callable[[], Awaitable[None]] | None = None
