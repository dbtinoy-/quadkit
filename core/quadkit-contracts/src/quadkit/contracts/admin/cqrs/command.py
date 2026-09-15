"""AdminCommand marker — base class for admin CQRS commands."""

from __future__ import annotations


class AdminCommand:
    """Marker base class for admin commands.

    Subclass this for every admin command object. No methods required —
    the class itself serves as the marker for CQRS routing.
    """


__all__ = ["AdminCommand"]
