"""Optional committed-read safety inspection, owned by each database adapter."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable


class CommittedReadState(StrEnum):
    """An adapter's synchronous assessment, not a transaction or read lease."""

    SAFE = "safe"
    UNSUPPORTED_PROVIDER = "unsupported_provider"
    UNSUPPORTED_POOL = "unsupported_pool"
    UNOBSERVABLE_TRANSACTION = "unobservable_transaction"
    IN_TRANSACTION = "in_transaction"


@runtime_checkable
class CommittedReadGuardProtocol(Protocol):
    """Opt-in safety contract for trusted database composition.

    Literal True advertises the versioned method, not a universal guarantee.
    SAFE requires the adapter's actual driver, pool and transaction machinery
    to preserve committed-only query execution, including across tasks. An
    instantaneous flag check alone cannot establish that property. Adapters
    must fail closed for unsupported implementations/configurations.

    Consumers cannot certify arbitrary Python implementations by shape or
    marker. Composition must supply a trusted adapter; this is not a security
    sandbox, authentication mechanism, transaction lock or delivery guarantee.
    """

    supports_committed_read_guard_v1: bool

    def committed_read_state(self) -> CommittedReadState:
        """Inspect adapter-owned safety without I/O or altering transaction state."""
        ...


__all__ = ["CommittedReadGuardProtocol", "CommittedReadState"]
