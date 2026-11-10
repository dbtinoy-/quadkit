"""Convention followed: **Domain models in domains/** — structured extraction
schemas are ``@dataclass`` classes inheriting from ``quadkit.domain.DomainModel``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quadkit.domain import DomainModel


@dataclass
class TicketBrief(DomainModel):
    """Structured triage brief parsed from an unstructured support note."""

    category: str = ""
    severity: str = ""
    summary: str = ""
    action_items: list[str] = field(default_factory=list)


__all__ = ["TicketBrief"]
