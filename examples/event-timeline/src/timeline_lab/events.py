"""The one event contract used by the lab."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.events.messages import Event


@dataclass(frozen=True)
class TimelineEvent(Event):
    """A fact in the lab's single checkout stream.

    This is deliberately a regular Quadkit ``Event`` subclass so the event
    store can assign sequence metadata and the event bus can route it to
    subscribers by type.
    """

    action: str = "open"
    note: str = ""
    stream_id: str = "checkout-demo"


__all__ = ["TimelineEvent"]
