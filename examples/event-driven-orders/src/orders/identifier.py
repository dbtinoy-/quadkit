"""Ambient identifier generation for the event-driven orders demo.

Uses the framework's ambient identity module — no DI needed.

Convention: ambient capabilities (clock, identity, hashing) are
process-level and exempt from constructor injection.  They live in their
own module so the rest of the codebase imports from a single source.
"""

from __future__ import annotations

from quadkit.identity import ambient as identity


def new_order_id() -> str:
    """Return a fresh order identifier."""
    return identity.generate_for("order")


__all__ = ["new_order_id"]
