"""Base message classes for Event Sourcing and CQRS.

Re-exports :class:`~quadkit.contracts.events.messages.Message` and
:class:`~quadkit.contracts.events.messages.MessageMetadata` from
``quadkit.contracts`` so that event-sourcing code has a single, stable
import path within the events package.
"""

from __future__ import annotations

from quadkit.contracts.events.messages import Message, MessageMetadata

__all__ = ["Message", "MessageMetadata"]
