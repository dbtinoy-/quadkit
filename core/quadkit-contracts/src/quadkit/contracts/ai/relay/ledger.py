"""Relay ledger contracts: quota credit-in records and service protocol.

The ledger is the framework's credit-in mechanism: it journals
top-up and check-in credits so operators (via ``relay.billing``
permissioned admin surfaces) and applications have an audited, single
mutation path for adding quota.  The framework records usage but no
wallet balance; applications compute or enforce balances from ledger
credits and usage records.  Check-in awards are caller-supplied —
award amounts and cadences are application policy, not framework
constants.  All mutations are idempotent or compare-and-set: a top-up
settles once (CAS on status), a check-in is PK-guaranteed once per
``(user_id, day)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Literal, Protocol, runtime_checkable

from quadkit.contracts.core.result import Result

if TYPE_CHECKING:
    from quadkit.contracts.ai.governance import RelayUsageScope

RelayTopUpStatus = Literal["pending", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class RelayTopUpRecord:
    """One quota credit-in record.

    Attributes:
        reference_id: Unique reference for the credit (primary key).
        user_id: User the credit applies to.
        amount: Credited amount as a Decimal string, never negative.
        status: ``pending`` (awaiting settlement), ``completed``, or
            ``failed``.
        created_at: ISO-8601 creation timestamp (UTC).
    """

    reference_id: str
    user_id: str
    amount: str
    status: RelayTopUpStatus
    created_at: str

    def __post_init__(self) -> None:
        """Reject empty identities, negative amounts, and bad statuses."""
        if not self.reference_id:
            raise ValueError("reference_id must be non-empty")
        if not self.user_id:
            raise ValueError("user_id must be non-empty")
        try:
            if float(self.amount) < 0:
                raise ValueError("amount must be non-negative")
        except ValueError as exc:
            raise ValueError("amount must be a non-negative number") from exc
        if self.status not in ("pending", "completed", "failed"):
            raise ValueError(f"unknown top-up status: {self.status}")


@dataclass(frozen=True, slots=True)
class RelayCheckinRecord:
    """One daily check-in award granted to a user.

    Attributes:
        user_id: User the award applies to.
        day: Award day in ISO ``YYYY-MM-DD`` (UTC).
        award: Awarded amount as a Decimal string, never negative.
        created_at: ISO-8601 creation timestamp (UTC).
    """

    user_id: str
    day: str
    award: str
    created_at: str

    def __post_init__(self) -> None:
        """Reject empty identities, bad dates, and negative awards."""
        if not self.user_id:
            raise ValueError("user_id must be non-empty")
        try:
            date.fromisoformat(self.day)
        except ValueError as exc:
            raise ValueError("day must be ISO YYYY-MM-DD") from exc
        try:
            if float(self.award) < 0:
                raise ValueError("award must be non-negative")
        except ValueError as exc:
            raise ValueError("award must be a non-negative number") from exc


@dataclass(frozen=True, slots=True)
class RelayLedgerError:
    """A domain error returned from ledger operations.

    Attributes:
        code: Machine-readable error code (``already_checked_in``,
            ``not_found``, ``stale_settlement``, ...).
        message: Public, redaction-safe error message.
    """

    code: str
    message: str


@runtime_checkable
class RelayLedgerServiceProtocol(Protocol):
    """Governance quota credit-in over the relay ledger.

    All mutations journal a record and emit a structured event;
    reservations and settled usage (Plan C) are never touched by this
    protocol.
    """

    async def credit(
        self, scope: RelayUsageScope, amount: str, reason: str
    ) -> Result[None, RelayLedgerError]:
        """Journal an immediate completed credit for *scope*."""
        ...

    async def settle_topup(
        self, reference_id: str, expected_status: str
    ) -> Result[None, RelayLedgerError]:
        """Flip *reference_id* from *expected_status* to completed exactly once."""
        ...

    async def checkin(
        self, user_id: str, award: str
    ) -> Result[RelayCheckinRecord, RelayLedgerError]:
        """Award *award* to *user_id* once per UTC day."""
        ...

    async def list_topups(
        self, user_id: str | None, limit: int
    ) -> list[RelayTopUpRecord]:
        """List top-up records, newest first, optionally for one user."""
        ...


__all__ = [
    "RelayCheckinRecord",
    "RelayLedgerError",
    "RelayLedgerServiceProtocol",
    "RelayTopUpRecord",
    "RelayTopUpStatus",
]
