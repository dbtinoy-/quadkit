"""Domain-driven design primitives package.

Organized into focused submodules:

* ``base`` – DomainModelProtocol and ID type variable
* ``events`` – DomainEvent and related helpers
* ``aggregates`` – AggregateRootProtocol (protocol only; implementation in ``quadkit.domain``)
* ``specification`` – SpecificationProtocol protocol

Note: DomainModel, Entity, and ValueObject implementations have moved to
``quadkit.domain.base``. Import from there instead.
Note: The concrete ``AggregateRoot`` base class lives in ``quadkit.domain.models.aggregate``.
"""

from __future__ import annotations

# re-export core domain primitives for convenience
from quadkit.contracts.domain.aggregates import AggregateRootProtocol
from quadkit.contracts.domain.base import (
    ID,
    DomainModelProtocol,
)
from quadkit.contracts.domain.events import DomainEvent
from quadkit.contracts.domain.idempotency import (
    IdempotencyRecord,
    IdempotencyStatus,
)
from quadkit.contracts.domain.pagination import (
    CursorPage,
    CursorPageProtocol,
    OffsetPageProtocol,
)
from quadkit.contracts.domain.specification import SpecificationProtocol

__all__: list[str] = [
    "ID",
    "AggregateRootProtocol",
    "CursorPage",
    "CursorPageProtocol",
    "DomainEvent",
    "DomainModelProtocol",
    "IdempotencyRecord",
    "IdempotencyStatus",
    "OffsetPageProtocol",
    "SpecificationProtocol",
]
