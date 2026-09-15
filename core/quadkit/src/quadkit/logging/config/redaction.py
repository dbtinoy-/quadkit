"""Log field redaction configuration for the logging subsystem."""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.domain import DomainModel
from quadkit.logging.redaction import _DEFAULT_FIELD_DENYLIST
from quadkit.validation import Field


@dataclass(init=False)
class RedactionConfig(DomainModel):
    """Configuration for log event field redaction.

    Attributes:
        enabled: Whether log field redaction is enabled. Defaults to True
            (safe by default).
        field_denylist: Field names masked with ``"<redacted>"`` when
            emitted in log events, matched case-insensitively. Defaults to
            the core ``_DEFAULT_FIELD_DENYLIST``.
    """

    enabled: bool = Field(default=True)
    field_denylist: tuple[str, ...] = Field(
        default_factory=lambda: tuple(_DEFAULT_FIELD_DENYLIST)
    )


__all__ = ["RedactionConfig"]
