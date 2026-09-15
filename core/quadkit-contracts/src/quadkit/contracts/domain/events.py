"""Domain event definitions."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


def _to_json_safe(value: Any) -> Any:
    """Convert a value to a JSON-serialisable primitive.

    Handles UUID → str and datetime → ISO-8601 str.  All other values
    are returned unchanged.
    """
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


@dataclass(init=False, frozen=True)
class DomainEvent:
    """Base class for domain events."""

    event_id: UUID = field(default_factory=uuid4, kw_only=True)
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(UTC), kw_only=True
    )

    # ---- event-sourcing fields ----
    event_type: str | None = field(default=None, kw_only=True)
    aggregate_id: UUID | None = field(default=None, kw_only=True)
    aggregate_type: str | None = field(default=None, kw_only=True)
    sequence_number: int | None = field(default=None, kw_only=True)
    actor_id: str | None = field(default=None, kw_only=True)

    # ---- schema evolution ----
    schema_version: int = field(
        default=1, kw_only=True
    )  # M-07: version of the event contract

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the event setting base fields and any extra subclass fields.

        Declared dataclass fields receive their default values when not
        supplied.  Extra keyword arguments (e.g. fields declared on plain
        subclasses without ``@dataclass``) are set directly on the instance
        via ``object.__setattr__``, which bypasses the ``frozen=True``
        guard safely during construction.
        """
        for f in dataclasses.fields(self):
            if f.name in kwargs:
                object.__setattr__(self, f.name, kwargs.pop(f.name))
            elif f.default is not dataclasses.MISSING:
                object.__setattr__(self, f.name, f.default)
            elif f.default_factory is not dataclasses.MISSING:
                object.__setattr__(self, f.name, f.default_factory())
        # Extra kwargs are subclass-specific fields not declared via @dataclass.
        for k, v in kwargs.items():
            object.__setattr__(self, k, v)
        self.__post_init__()

    def __post_init__(self) -> None:
        # lifecycle hook
        if self.event_type is None:
            object.__setattr__(self, "event_type", self.__class__.__name__)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {k: _to_json_safe(v) for k, v in dataclasses.asdict(self).items()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DomainEvent:
        return cls(**data)

    def for_aggregate(self, aggregate_id: UUID, aggregate_type: str) -> DomainEvent:
        return replace(
            self,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
        )


__all__ = ["DomainEvent"]
