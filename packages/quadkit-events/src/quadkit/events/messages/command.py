"""Command message classes for Event Sourcing and CQRS.

Defines :class:`Command` and :class:`IdempotentCommand` by extending their
contract counterparts with aggregate-targeting helpers (``target_aggregate_id``,
``expected_version``, ``for_aggregate``).  These are the concrete types that
application code sends through the command bus.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.events.messages import Command as _Command
from quadkit.contracts.events.messages import IdempotentCommand as _IdempotentCommand

if TYPE_CHECKING:
    from uuid import UUID


class Command(_Command):
    """Command extended with aggregate-targeting helpers."""

    @property
    def target_aggregate_id(self) -> UUID | None:
        return self.metadata.custom.get("target_aggregate_id")

    @property
    def expected_version(self) -> int | None:
        return self.metadata.custom.get("expected_version")

    def for_aggregate(self, aggregate_id: UUID, version: int | None = None) -> Command:
        """Target a specific aggregate."""
        cmd: Command = self.with_metadata(  # type: ignore[assignment]
            self.metadata.with_custom("target_aggregate_id", aggregate_id),
        )
        if version is not None:
            cmd = cmd.with_metadata(  # type: ignore[assignment]
                cmd.metadata.with_custom("expected_version", version),
            )
        return cmd


class IdempotentCommand(_IdempotentCommand, Command):
    """Idempotent command extended with aggregate-targeting helpers."""


__all__ = ["Command", "IdempotentCommand"]
