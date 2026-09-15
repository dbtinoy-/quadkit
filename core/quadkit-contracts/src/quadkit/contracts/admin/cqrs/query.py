"""AdminQuery marker — base class for admin CQRS queries."""

from __future__ import annotations


class AdminQuery:
    """Marker base class for admin queries.

    Subclass this for every admin query object. No methods required —
    the class itself serves as the marker for CQRS routing.
    """


__all__ = ["AdminQuery"]
